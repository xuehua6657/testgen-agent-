"""Tests for TestGen-Agent data models."""

from testgen.models import (
    AnalysisResult,
    CodeChange,
    GeneratedTest,
    TestSpec,
    ValidationResult,
)


class TestCodeChange:
    def test_create(self):
        change = CodeChange(
            file_path="src/example.py",
            diff_text="diff --git a/src/example.py b/src/example.py",
            added_lines=[1, 2, 3],
            removed_lines=[],
            changed_functions=["hello_world"],
            language="python",
        )

        assert change.file_path == "src/example.py"
        assert change.language == "python"
        assert len(change.added_lines) == 3


class TestAnalysisResult:
    def test_create(self):
        change = CodeChange(
            file_path="src/example.py",
            diff_text="diff",
            added_lines=[1],
            removed_lines=[],
            changed_functions=["func"],
            language="python",
        )

        result = AnalysisResult(
            changes=[change],
            summary="Found 1 changed file",
            affected_modules=["src/example.py"],
            risk_level="low",
        )

        assert len(result.changes) == 1
        assert result.risk_level == "low"


class TestTestSpec:
    def test_create(self):
        spec = TestSpec(
            source_file="src/example.py",
            target_function="hello_world",
            test_type="unit",
            description="Test hello_world function",
            input_params={"name": "str"},
            expected_behavior="Returns greeting string",
        )

        assert spec.source_file == "src/example.py"
        assert spec.target_function == "hello_world"
        assert spec.test_type == "unit"


class TestGeneratedTest:
    def test_create(self):
        spec = TestSpec(
            source_file="src/example.py",
            target_function="hello_world",
            test_type="unit",
            description="Test",
            input_params={},
            expected_behavior="Works",
        )

        test = GeneratedTest(
            test_spec=spec,
            test_code="def test_hello(): pass",
            file_path="tests/test_example.py",
            is_new_file=True,
            confidence=0.85,
        )

        assert test.is_new_file is True
        assert test.confidence == 0.85


class TestValidationResult:
    def test_create(self):
        result = ValidationResult(
            test_index=0,
            passed=True,
            score=0.9,
            errors=[],
        )

        assert result.passed is True
        assert result.score == 0.9
        assert result.errors == []

    def test_failed(self):
        result = ValidationResult(
            test_index=0,
            passed=False,
            score=0.3,
            errors=["Syntax error at line 5"],
        )

        assert result.passed is False
        assert len(result.errors) == 1
