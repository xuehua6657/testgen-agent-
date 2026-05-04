"""Tests for TestGen-Agent prompts."""

from testgen.models import CodeChange
from testgen.prompt import (
    SYSTEM_PROMPT,
    VALIDATION_PROMPT,
    SUMMARY_PROMPT,
    build_test_generation_prompt,
    build_test_generation_prompt_batch,
)


class TestSystemPrompt:
    def test_contains_rules(self):
        assert "unit test" in SYSTEM_PROMPT.lower()
        assert "Rules:" in SYSTEM_PROMPT
        assert "{framework}" in SYSTEM_PROMPT
        assert "{language}" in SYSTEM_PROMPT


class TestValidationPrompt:
    def test_placeholders(self):
        assert "{source_code}" in VALIDATION_PROMPT
        assert "{test_code}" in VALIDATION_PROMPT
        assert "0.0 to 1.0" in VALIDATION_PROMPT


class TestSummaryPrompt:
    def test_placeholders(self):
        assert "{changes}" in SUMMARY_PROMPT


class TestBuildTestGenerationPrompt:
    def test_basic_prompt(self):
        change = CodeChange(
            file_path="src/example.py",
            diff_text="+def hello(): pass",
            added_lines=[1],
            removed_lines=[],
            changed_functions=["hello"],
            language="python",
        )

        prompt = build_test_generation_prompt(
            change=change,
            source_code="def hello(): pass",
        )

        assert "## Code Change: src/example.py" in prompt
        assert "### Diff:" in prompt
        assert "### Full Source Code:" in prompt
        assert "### Changed Functions/Methods: hello" in prompt

    def test_with_existing_tests(self):
        change = CodeChange(
            file_path="src/example.py",
            diff_text="+def hello(): pass",
            added_lines=[1],
            removed_lines=[],
            changed_functions=["hello"],
            language="python",
        )

        prompt = build_test_generation_prompt(
            change=change,
            source_code="def hello(): pass",
            existing_tests="def test_hello(): pass",
        )

        assert "### Existing Tests (match this style):" in prompt
        assert "def test_hello(): pass" in prompt

    def test_custom_config(self):
        change = CodeChange(
            file_path="src/example.py",
            diff_text="+def hello(): pass",
            added_lines=[1],
            removed_lines=[],
            changed_functions=["hello"],
            language="python",
        )

        prompt = build_test_generation_prompt(
            change=change,
            source_code="def hello(): pass",
            config_language="javascript",
            config_framework="jest",
        )

        assert "jest framework" in prompt
        assert "javascript syntax" in prompt


class TestBuildTestGenerationPromptBatch:
    def test_batch_prompt(self):
        changes = [
            CodeChange(
                file_path="src/a.py",
                diff_text="+def func_a(): pass",
                added_lines=[1],
                removed_lines=[],
                changed_functions=["func_a"],
                language="python",
            ),
            CodeChange(
                file_path="src/b.py",
                diff_text="+def func_b(): pass",
                added_lines=[1],
                removed_lines=[],
                changed_functions=["func_b"],
                language="python",
            ),
        ]

        prompt = build_test_generation_prompt_batch(
            changes=changes,
            source_codes={"src/a.py": "def func_a(): pass", "src/b.py": "def func_b(): pass"},
            existing_tests_map={},
        )

        assert "## Batch Test Generation Request" in prompt
        assert "Generate unit tests for 2 changed files" in prompt
        assert "### Change 1: src/a.py" in prompt
        assert "### Change 2: src/b.py" in prompt
        assert "# === Tests for <filename> ===" in prompt
