"""Tests for TestGen-Agent configuration."""

import os
import tempfile
from pathlib import Path

import pytest

from testgen.config import (
    DEFAULT_CONFIG_TEMPLATE,
    AgentConfig,
    CIConfig,
    LLMConfig,
    TestGenConfig,
)


class TestLLMConfig:
    def test_from_env_with_api_key(self, monkeypatch):
        monkeypatch.setenv("TESTGEN_LLM_API_KEY", "test-key-123")
        monkeypatch.setenv("TESTGEN_LLM_MODEL", "gpt-4o-mini")

        config = LLMConfig.from_env()

        assert config.model == "gpt-4o-mini"
        assert config.api_key.get_secret_value() == "test-key-123"

    def test_from_env_without_api_key(self, monkeypatch):
        monkeypatch.delenv("TESTGEN_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="API key not found"):
            LLMConfig.from_env()

    def test_default_values(self):
        config = LLMConfig(api_key="test-key")

        assert config.model == "gpt-4o"
        assert config.temperature == 0.2
        assert config.max_tokens == 4096
        assert config.base_url is None


class TestAgentConfig:
    def test_default_values(self):
        config = AgentConfig()

        assert config.max_iterations == 3
        assert config.max_tests_per_file == 10
        assert config.min_confidence_score == 0.7
        assert config.include_docstrings is True

    def test_custom_values(self):
        config = AgentConfig(
            max_iterations=5,
            max_tests_per_file=20,
            min_confidence_score=0.9,
        )

        assert config.max_iterations == 5
        assert config.max_tests_per_file == 20
        assert config.min_confidence_score == 0.9


class TestTestGenConfig:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("TESTGEN_LLM_API_KEY", "test-key")

        config = TestGenConfig.from_env()

        assert config.llm.api_key.get_secret_value() == "test-key"
        assert config.target_language == "python"
        assert config.test_framework == "pytest"

    def test_from_file(self, monkeypatch):
        monkeypatch.setenv("TESTGEN_LLM_API_KEY", "env-key")

        config_content = """\
llm:
  model: claude-sonnet-4-6
  temperature: 0.3

agent:
  max_iterations: 5

target_language: python
test_framework: pytest
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(config_content)
            f.flush()
            config = TestGenConfig.from_file(f.name)

        assert config.llm.model == "claude-sonnet-4-6"
        assert config.llm.temperature == 0.3
        assert config.agent.max_iterations == 5

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            TestGenConfig.from_file("/nonexistent/path.yaml")

    def test_to_yaml(self, monkeypatch):
        monkeypatch.setenv("TESTGEN_LLM_API_KEY", "test-key")

        config = TestGenConfig.from_env()
        yaml_str = config.to_yaml()

        assert "llm:" in yaml_str
        assert "agent:" in yaml_str
        assert "gpt-4o" in yaml_str

    def test_to_yaml_writes_file(self, monkeypatch):
        monkeypatch.setenv("TESTGEN_LLM_API_KEY", "test-key")

        config = TestGenConfig.from_env()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            config.to_yaml(f.name)
            content = Path(f.name).read_text()

        assert "llm:" in content


class TestDefaultConfigTemplate:
    def test_is_valid_yaml(self):
        import yaml

        data = yaml.safe_load(DEFAULT_CONFIG_TEMPLATE)
        assert "llm" in data
        assert "agent" in data
        assert "ci" in data
