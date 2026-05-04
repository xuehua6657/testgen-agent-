"""Tests for TestGen-Agent validator."""

from testgen.config import TestGenConfig
from testgen.validator import TestValidator


def make_config():
    """Create a TestGenConfig for testing."""
    return TestGenConfig(
        llm={
            "api_key": "test-key-123",
            "model": "gpt-4o",
        }
    )


class TestTestValidator:
    def setup_method(self):
        self.config = make_config()
        self.validator = TestValidator(self.config)

    def test_syntax_check_valid(self):
        code = "def test_hello():\n    assert True"
        is_valid, error = self.validator.syntax_check(code)
        assert is_valid is True
        assert error is None

    def test_syntax_check_invalid(self):
        code = "def test_hello(\n    assert True"
        is_valid, error = self.validator.syntax_check(code)
        assert is_valid is False
        assert error is not None
        assert "Syntax error" in error

    def test_syntax_check_empty(self):
        is_valid, error = self.validator.syntax_check("")
        assert is_valid is True

    def test_import_check_valid(self):
        code = "import os\n\ndef test_path():\n    assert os.path.exists('/')"
        is_valid, error = self.validator.import_check(code)
        assert is_valid is True

    def test_import_check_obviously_invalid(self):
        code = "from nonexistent_module_fake import something"
        is_valid, error = self.validator.import_check(code)
        # This should be caught by our heuristic
        assert is_valid is False

    def test_full_validate_valid_code(self):
        code = """\
def test_add():
    assert 1 + 1 == 2

def test_subtract():
    assert 5 - 3 == 2
"""
        is_valid, score, errors = self.validator.validate(code)
        assert is_valid is True
        assert score >= 0.5
        assert errors == []

    def test_full_validate_invalid_code(self):
        code = "def testBroken(\n    syntax error here"
        is_valid, score, errors = self.validator.validate(code)
        assert is_valid is False
        assert score == 0.0
        assert len(errors) >= 1
