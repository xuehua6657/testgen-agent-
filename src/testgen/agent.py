"""LangGraph agent workflow for TestGen-Agent."""

from pathlib import Path

from langgraph.graph import END, StateGraph

from testgen.analyzer import CodeAnalyzer
from testgen.config import TestGenConfig
from testgen.generator import TestGenerator
from testgen.models import (
    AgentState,
    GeneratedTest,
    TestSpec,
    ValidationResult,
)
from testgen.prompt import (
    SYSTEM_PROMPT,
    build_test_generation_prompt,
    build_test_generation_prompt_batch,
)
from testgen.utils import get_logger, safe_write_file
from testgen.validator import TestValidator


class TestGenAgent:
    """Main agent that orchestrates the test generation workflow."""

    def __init__(self, config: TestGenConfig):
        self.config = config
        self.logger = get_logger()
        self.analyzer = CodeAnalyzer(config)
        self.generator = TestGenerator(config.llm)
        self.validator = TestValidator(config)
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the LangGraph workflow.

        Workflow:
            START -> analyze -> specify_tests -> generate -> validate
                                                            |
                                    +--> retry (if failed, iteration < max)
                                    +--> save (if valid tests)
                                    +--> END (if all fail)
        """
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze", self._analyze_changes)
        workflow.add_node("specify_tests", self._create_test_specs)
        workflow.add_node("generate", self._generate_tests)
        workflow.add_node("validate", self._validate_tests)
        workflow.add_node("save", self._save_tests)

        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "specify_tests")
        workflow.add_edge("specify_tests", "generate")
        workflow.add_edge("generate", "validate")

        workflow.add_conditional_edges(
            "validate",
            self._should_retry,
            {
                "retry": "generate",
                "save": "save",
                "end": END,
            },
        )
        workflow.add_edge("save", END)

        return workflow.compile()

    def _analyze_changes(self, state: AgentState) -> dict:
        """Node: Parse git diff and analyze changes."""
        self.logger.info("Analyzing code changes...")
        diff_text = state.get("diff_text", "")

        if not diff_text:
            self.logger.error("No diff text provided")
            return {"errors": ["No diff text provided"]}

        analysis = self.analyzer.run(diff_text, state.get("repo_path", "."))

        self.logger.info(f"Analysis complete: {analysis.summary}")
        return {
            "analysis": analysis,
            "errors": [],
        }

    def _create_test_specs(self, state: AgentState) -> dict:
        """Node: Create test specifications from analysis."""
        analysis = state.get("analysis")
        if not analysis or not analysis.changes:
            return {"test_specs": [], "errors": ["No changes to generate tests for"]}

        specs: list[TestSpec] = []

        for change in analysis.changes:
            if change.language != "python":
                self.logger.warning(
                    f"Skipping non-Python file: {change.file_path} ({change.language})"
                )
                continue

            for func in change.changed_functions:
                spec = TestSpec(
                    source_file=change.file_path,
                    target_function=func,
                    test_type="unit",
                    description=f"Test {func} in {change.file_path}",
                    input_params={},
                    expected_behavior=f"{func} behaves correctly",
                )
                specs.append(spec)

        # Limit tests per config
        max_tests = self.config.agent.max_tests_per_file
        if len(specs) > max_tests:
            self.logger.info(f"Limiting to {max_tests} test specs")
            specs = specs[:max_tests]

        self.logger.info(f"Created {len(specs)} test specifications")
        return {"test_specs": specs}

    def _generate_tests(self, state: AgentState) -> dict:
        """Node: Generate test code for each spec."""
        analysis = state.get("analysis")
        test_specs = state.get("test_specs", [])
        iteration = state.get("iteration", 0)

        if not test_specs:
            return {"generated_tests": [], "iteration": iteration + 1}

        self.logger.info(
            f"Generating tests (iteration {iteration + 1}) for {len(test_specs)} specs..."
        )

        # Build batch prompt
        source_codes: dict[str, str] = {}
        existing_tests_map: dict[str, str] = {}

        for change in analysis.changes if analysis else []:
            repo_path = Path(state.get("repo_path", "."))
            context = self.analyzer.analyze_context(change, repo_path)
            source_codes[change.file_path] = context["source_code"]
            if context["existing_tests"]:
                existing_tests_map[change.file_path] = context["existing_tests"]

        system_prompt = SYSTEM_PROMPT.format(
            framework=self.config.test_framework,
            language=self.config.target_language,
        )

        prompt = build_test_generation_prompt_batch(
            changes=analysis.changes if analysis else [],
            source_codes=source_codes,
            existing_tests_map=existing_tests_map,
            config_language=self.config.target_language,
            config_framework=self.config.test_framework,
        )

        try:
            response = self.generator.generate_with_retry(
                prompt, system_prompt, max_retries=2
            )
        except RuntimeError as e:
            self.logger.error(f"Test generation failed: {e}")
            return {
                "generated_tests": [],
                "errors": [str(e)],
                "iteration": iteration + 1,
            }

        # Parse response into individual test files
        generated_tests: list[GeneratedTest] = []

        # Try to split by file marker
        file_sections = response.split("# === Tests for ")
        for section in file_sections[1:] if len(file_sections) > 1 else [response]:
            if "# === Tests for " in section:
                header, code = section.split("\n", 1)
                file_name = header.split(" ===")[0].strip()
            else:
                # Single file or no header - use first change's file
                file_name = (
                    analysis.changes[0].file_path
                    if analysis and analysis.changes
                    else "test_generated.py"
                )
                code = section

            # Derive test file name
            source_path = Path(file_name)
            test_name = f"test_{source_path.stem}.py"
            test_path = str(Path(self.config.test_dirs[0]) / test_name)

            # Check if this is a new file or appending to existing
            repo_path = Path(state.get("repo_path", "."))
            full_path = repo_path / test_path
            is_new = not full_path.exists()

            # Find matching spec
            matching_specs = [
                s for s in test_specs if s.source_file == file_name
            ]

            generated_tests.append(
                GeneratedTest(
                    test_spec=matching_specs[0] if matching_specs else test_specs[0],
                    test_code=code.strip(),
                    file_path=test_path,
                    is_new_file=is_new,
                    confidence=0.0,  # Will be set during validation
                )
            )

        self.logger.info(f"Generated {len(generated_tests)} test file(s)")
        return {
            "generated_tests": generated_tests,
            "iteration": iteration + 1,
        }

    def _validate_tests(self, state: AgentState) -> dict:
        """Node: Validate generated tests."""
        generated_tests = state.get("generated_tests", [])
        analysis = state.get("analysis")

        if not generated_tests:
            return {
                "validation_results": [],
                "errors": ["No tests to validate"],
            }

        self.logger.info(f"Validating {len(generated_tests)} test file(s)...")

        validation_results: list[ValidationResult] = []

        for i, test in enumerate(generated_tests):
            # Get source code for this test
            source_code = ""
            if analysis:
                for change in analysis.changes:
                    if change.file_path == test.test_spec.source_file:
                        repo_path = Path(state.get("repo_path", "."))
                        context = self.analyzer.analyze_context(change, repo_path)
                        source_code = context["source_code"]
                        break

            is_valid, score, errors = self.validator.validate(
                test_code=test.test_code,
                source_code=source_code,
                generator=self.generator,
            )

            result = ValidationResult(
                test_index=i,
                passed=is_valid,
                score=score,
                errors=errors,
            )
            validation_results.append(result)

            # Update confidence on test
            test.confidence = score

            status = "PASS" if is_valid else "FAIL"
            self.logger.info(
                f"  {test.file_path}: {status} (score: {score:.2f})"
            )
            if errors:
                for err in errors:
                    self.logger.warning(f"    - {err}")

        passed_count = sum(1 for r in validation_results if r.passed)
        self.logger.info(
            f"Validation complete: {passed_count}/{len(validation_results)} passed"
        )

        return {"validation_results": validation_results}

    def _should_retry(self, state: AgentState) -> str:
        """Conditional: Decide whether to retry, save, or fail."""
        validation_results = state.get("validation_results", [])
        iteration = state.get("iteration", 0)
        max_iterations = self.config.agent.max_iterations

        if not validation_results:
            if iteration >= max_iterations:
                self.logger.error("Max iterations reached with no tests generated")
                return "end"
            self.logger.info("No tests to validate, retrying generation...")
            return "retry"

        passed_count = sum(1 for r in validation_results if r.passed)

        if passed_count > 0:
            # At least some tests passed, save them
            self.logger.info(f"{passed_count} tests passed, saving...")
            return "save"

        if iteration >= max_iterations:
            self.logger.error(
                f"Max iterations ({max_iterations}) reached, all tests failed"
            )
            return "end"

        self.logger.info(
            f"All tests failed, retrying (iteration {iteration}/{max_iterations})..."
        )
        return "retry"

    def _save_tests(self, state: AgentState) -> dict:
        """Node: Write valid tests to files."""
        generated_tests = state.get("generated_tests", [])
        validation_results = state.get("validation_results", [])
        repo_path = Path(state.get("repo_path", "."))

        saved_count = 0
        for i, test in enumerate(generated_tests):
            result = validation_results[i] if i < len(validation_results) else None

            if result and not result.passed:
                self.logger.warning(f"Skipping failed test: {test.file_path}")
                continue

            full_path = repo_path / test.file_path
            if safe_write_file(full_path, test.test_code):
                self.logger.info(f"Saved: {test.file_path}")
                saved_count += 1
            else:
                self.logger.error(f"Failed to save: {test.file_path}")

        output_path = str(repo_path / self.config.test_dirs[0])
        self.logger.info(f"Saved {saved_count} test file(s) to {output_path}")

        return {"final_output_path": output_path}

    def run(self, repo_path: str, ref: str = "HEAD") -> dict:
        """Execute the full test generation workflow.

        Args:
            repo_path: Path to git repository.
            ref: Git ref to diff against.

        Returns:
            Final agent state with results.
        """
        from testgen.utils import extract_full_diff

        self.logger.info(f"Starting test generation for {repo_path} (ref: {ref})")

        # Extract diff
        diff_text = extract_full_diff(repo_path, ref)
        if not diff_text.strip():
            self.logger.info("No changes detected, nothing to do")
            return {"errors": ["No changes detected"]}

        # Initialize state
        initial_state: AgentState = {
            "repo_path": repo_path,
            "ref": ref,
            "diff_text": diff_text,
            "analysis": None,
            "test_specs": [],
            "generated_tests": [],
            "validation_results": [],
            "errors": [],
            "iteration": 0,
            "final_output_path": None,
        }

        # Run workflow
        final_state = self.graph.invoke(initial_state)

        # Report results
        if final_state.get("final_output_path"):
            self.logger.info(f"Done! Tests saved to {final_state['final_output_path']}")
        else:
            self.logger.warning("No tests were generated")

        return final_state
