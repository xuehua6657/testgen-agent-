"""Tests for TestGen-Agent generator."""

from unittest.mock import MagicMock, patch

import pytest

from testgen.config import LLMConfig
from testgen.generator import TestGenerator


def make_llm_config():
    """Create an LLMConfig for testing."""
    return LLMConfig(api_key="test-key-123")


class TestTestGenerator:
    def setup_method(self):
        self.config = make_llm_config()

    def test_extract_code_python_fence(self):
        generator = TestGenerator(self.config)
        response = "```python\ndef test_hello():\n    assert True\n```"
        blocks = generator.extract_code(response, "python")
        assert len(blocks) == 1
        assert "def test_hello():" in blocks[0]

    def test_extract_code_generic_fence(self):
        generator = TestGenerator(self.config)
        response = "```\ndef test_hello():\n    assert True\n```"
        blocks = generator.extract_code(response, "python")
        assert len(blocks) == 1
        assert "def test_hello():" in blocks[0]

    def test_extract_code_no_fence(self):
        generator = TestGenerator(self.config)
        response = "def test_hello():\n    assert True"
        blocks = generator.extract_code(response, "python")
        assert len(blocks) == 1
        assert response in blocks[0]

    def test_extract_code_empty(self):
        generator = TestGenerator(self.config)
        blocks = generator.extract_code("", "python")
        assert blocks == []

    def test_extract_code_multiple_blocks(self):
        generator = TestGenerator(self.config)
        response = (
            "```python\ndef test_a(): pass\n```\n\n"
            "```python\ndef test_b(): pass\n```"
        )
        blocks = generator.extract_code(response, "python")
        assert len(blocks) == 2

    @patch("testgen.generator.OpenAI")
    def test_generate_tests_success(self, mock_openai):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "def test_example(): pass"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = TestGenerator(self.config)
        result = generator.generate_tests("prompt", "system")

        assert result == "def test_example(): pass"
        mock_client.chat.completions.create.assert_called_once()

    @patch("testgen.generator.OpenAI")
    def test_generate_with_retry_success(self, mock_openai):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "def test_example(): pass"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = TestGenerator(self.config)
        result = generator.generate_with_retry("prompt", "system", max_retries=2)

        assert result == "def test_example(): pass"

    @patch("testgen.generator.OpenAI")
    def test_generate_with_retry_exhausted(self, mock_openai):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")
        mock_openai.return_value = mock_client

        generator = TestGenerator(self.config)

        with pytest.raises(RuntimeError, match="after 2 attempts"):
            generator.generate_with_retry("prompt", "system", max_retries=2)
