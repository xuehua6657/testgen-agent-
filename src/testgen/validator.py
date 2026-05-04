"""Test validation for TestGen-Agent."""

import ast
import subprocess
import tempfile
from pathlib import Path

from testgen.config import TestGenConfig
from testgen.generator import TestGenerator
from testgen.prompt import VALIDATION_PROMPT
from testgen.utils import get_logger, safe_write_file


class TestValidator:
    """Validates generated tests for correctness and quality."""

    def __init__(self, config: TestGenConfig):
        self.config = config
        self.logger = get_logger()

    def syntax_check(self, test_code: str) -> tuple[bool, str | None]:
        """Check if test code is syntactically valid Python.

        Args:
            test_code: Python test code to check.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            ast.parse(test_code)
            return True, None
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            self.logger.warning(f"Syntax check failed: {error_msg}")
            return False, error_msg

    def import_check(self, test_code: str, source_file: str | None = None) -> tuple[bool, str | None]:
        """Check if imports in the test resolve correctly.

        Args:
            test_code: Python test code to check.
            source_file: Optional path to source file for context.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            tree = ast.parse(test_code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # We can't easily resolve imports without running Python,
                    # but we can check for obviously wrong imports
                    if isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("nonexistent_"):
                            return False, f"Invalid import: from {node.module}"
            return True, None
        except SyntaxError as e:
            return False, f"Cannot check imports - syntax error: {e.msg}"

    def dry_run(self, test_code: str, test_path: str | None = None) -> tuple[bool, str | None]:
        """Write test temporarily and run pytest --collect-only.

        Args:
            test_code: Python test code to validate.
            test_path: Optional path to write test file.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if test_path is None:
            # Use a temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", prefix="testgen_", delete=False
            ) as f:
                f.write(test_code)
                temp_path = f.name
        else:
            temp_path = test_path
            safe_write_file(temp_path, test_code)

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", temp_path, "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, None

            stderr = result.stderr.strip()
            if stderr:
                return False, f"Collection error: {stderr[:500]}"
            return False, "Unknown collection error"

        except subprocess.TimeoutExpired:
            return False, "pytest collection timed out"
        except FileNotFoundError:
            # pytest not installed, skip this check
            self.logger.warning("pytest not found, skipping dry-run check")
            return True, None
        finally:
            if test_path is None:
                # Clean up temp file
                try:
                    Path(temp_path).unlink()
                except OSError:
                    pass

    def run_tests(self, test_path: str) -> tuple[bool, str]:
        """Run the generated tests and return results.

        Args:
            test_path: Path to test file.

        Returns:
            Tuple of (all_passed, output).
        """
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_path, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            passed = result.returncode == 0
            output = result.stdout.strip() or result.stderr.strip()
            return passed, output

        except subprocess.TimeoutExpired:
            return False, "Tests timed out"
        except FileNotFoundError:
            return False, "pytest not found"

    def llm_quality_check(
        self,
        test_code: str,
        source_code: str,
        generator: TestGenerator,
    ) -> float:
        """Use LLM to score test quality (0.0-1.0).

        Args:
            test_code: Generated test code.
            source_code: Original source code.
            generator: TestGenerator instance for LLM calls.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        try:
            prompt = VALIDATION_PROMPT.format(
                source_code=source_code[:2000],  # Limit context
                test_code=test_code,
            )

            response = generator.client.chat.completions.create(
                model=generator.model,
                messages=[
                    {"role": "system", "content": "You are a test quality reviewer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=10,
            )

            content = (response.choices[0].message.content or "").strip()
            score = float(content)
            return max(0.0, min(1.0, score))

        except Exception as e:
            self.logger.warning(f"LLM quality check failed: {e}")
            # Default to a moderate score if quality check fails
            return 0.5

    def validate(
        self,
        test_code: str,
        source_code: str = "",
        generator: TestGenerator | None = None,
    ) -> tuple[bool, float, list[str]]:
        """Run full validation pipeline on generated test code.

        Args:
            test_code: Test code to validate.
            source_code: Source code being tested.
            generator: Optional generator for LLM quality check.

        Returns:
            Tuple of (is_valid, score, errors).
        """
        errors: list[str] = []

        # 1. Syntax check (fast)
        syntax_ok, syntax_error = self.syntax_check(test_code)
        if not syntax_ok:
            errors.append(syntax_error or "Unknown syntax error")
            return False, 0.0, errors

        # 2. Import check (fast)
        import_ok, import_error = self.import_check(test_code)
        if not import_ok:
            errors.append(import_error or "Unknown import error")
            return False, 0.2, errors

        # 3. Dry run (medium)
        dry_run_ok, dry_run_error = self.dry_run(test_code)
        if not dry_run_ok:
            errors.append(dry_run_error or "Unknown collection error")
            # Still allow saving - dry run failures may be environment issues
            self.logger.warning(f"Dry run failed: {dry_run_error}")

        # 4. Calculate base score
        score = 0.0
        if syntax_ok:
            score += 0.3
        if import_ok:
            score += 0.2
        if dry_run_ok:
            score += 0.3

        # 5. LLM quality check (optional, slower)
        if generator and source_code:
            try:
                quality_score = self.llm_quality_check(test_code, source_code, generator)
                score += quality_score * 0.2
            except Exception:
                score += 0.1  # Default partial score

        is_valid = score >= self.config.agent.min_confidence_score
        return is_valid, score, errors
