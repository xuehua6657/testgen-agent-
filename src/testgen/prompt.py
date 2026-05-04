"""System prompts and templates for test generation."""

from testgen.models import CodeChange

SYSTEM_PROMPT = """\
You are an expert software test engineer specializing in automated unit test generation.

Your task is to analyze code changes and generate comprehensive, high-quality unit tests.

Rules:
1. Generate tests using the {framework} framework
2. Tests should be written in {language}
3. Include clear docstrings explaining what each test verifies
4. Use descriptive test function names following the pattern: test_<function>_<scenario>_<expected>
5. Cover edge cases, boundary conditions, and error paths
6. Use mocking appropriately for external dependencies
7. Include type hints where appropriate
8. Tests must be self-contained and independently runnable
9. Do not modify the source code, only generate tests
10. Generate ONLY the test code, no explanations or markdown fences
"""

VALIDATION_PROMPT = """\
Review the following generated test code for quality and correctness.

Source code:
{source_code}

Generated test:
{test_code}

Rate the test quality from 0.0 to 1.0 based on:
- Coverage of the source function's behavior
- Edge case handling
- Code clarity and maintainability
- Proper assertions

Respond with ONLY a single float number between 0.0 and 1.0.
"""

SUMMARY_PROMPT = """\
Summarize the following code changes in 2-3 sentences for a developer.

Changes:
{changes}

Focus on what was changed and why it matters.
"""


def build_test_generation_prompt(
    change: CodeChange,
    source_code: str,
    existing_tests: str | None = None,
    config_language: str = "python",
    config_framework: str = "pytest",
) -> str:
    """Build the complete prompt for generating tests for a code change.

    Args:
        change: The code change to generate tests for.
        source_code: Full source file content.
        existing_tests: Existing test file content for style matching.
        config_language: Target programming language.
        config_framework: Test framework to use.

    Returns:
        Complete prompt string.
    """
    parts = [
        f"## Code Change: {change.file_path}",
        "",
        "### Diff:",
        change.diff_text,
        "",
        "### Full Source Code:",
        source_code,
        "",
        f"### Changed Functions/Methods: {', '.join(change.changed_functions) or 'unknown'}",
        "",
    ]

    if existing_tests:
        parts.extend([
            "### Existing Tests (match this style):",
            existing_tests,
            "",
        ])

    parts.extend([
        f"### Task:",
        f"Generate unit tests for the changed functions in {change.file_path}.",
        f"Use {config_framework} framework with {config_language} syntax.",
        "",
        f"Output ONLY the test code. No explanations.",
    ])

    return "\n".join(parts)


def build_test_generation_prompt_batch(
    changes: list[CodeChange],
    source_codes: dict[str, str],
    existing_tests_map: dict[str, str],
    config_language: str = "python",
    config_framework: str = "pytest",
) -> str:
    """Build a batch prompt for generating tests for multiple changes.

    Args:
        changes: List of code changes.
        source_codes: Map of file path to source code.
        existing_tests_map: Map of file path to existing test code.
        config_language: Target programming language.
        config_framework: Test framework to use.

    Returns:
        Complete batch prompt string.
    """
    parts = [
        "## Batch Test Generation Request",
        "",
        f"Generate unit tests for {len(changes)} changed files.",
        f"Use {config_framework} framework with {config_language} syntax.",
        "",
    ]

    for i, change in enumerate(changes, 1):
        source_code = source_codes.get(change.file_path, "")
        existing = existing_tests_map.get(change.file_path)

        parts.extend([
            f"### Change {i}: {change.file_path}",
            "",
            "#### Diff:",
            change.diff_text,
            "",
        ])

        if source_code:
            parts.extend(["#### Source Code:", source_code, ""])

        if existing:
            parts.extend(["#### Existing Tests (match style):", existing, ""])

        changed_funcs = ", ".join(change.changed_functions) or "unknown"
        parts.extend([
            f"#### Changed: {changed_funcs}",
            "",
        ])

    parts.extend([
        "### Output Format:",
        "Generate test code for EACH changed file. Separate each file's tests with a comment:",
        f'# === Tests for <filename> ===',
        "",
        "Output ONLY the test code. No explanations.",
    ])

    return "\n".join(parts)
