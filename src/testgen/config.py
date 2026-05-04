"""Configuration management for TestGen-Agent."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    model: str = Field(default="gpt-4o", description="LLM model name")
    base_url: str | None = Field(default=None, description="API base URL for non-OpenAI providers")
    api_key: SecretStr
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout: int = Field(default=120, gt=0)

    model_config = ConfigDict(env_prefix="TESTGEN_LLM_")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        api_key = os.environ.get("TESTGEN_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM API key not found. Set TESTGEN_LLM_API_KEY or OPENAI_API_KEY environment variable."
            )
        return cls(
            model=os.environ.get("TESTGEN_LLM_MODEL", "gpt-4o"),
            base_url=os.environ.get("TESTGEN_LLM_BASE_URL"),
            api_key=api_key,
            temperature=float(os.environ.get("TESTGEN_LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.environ.get("TESTGEN_LLM_MAX_TOKENS", "4096")),
            timeout=int(os.environ.get("TESTGEN_LLM_TIMEOUT", "120")),
        )


class AgentConfig(BaseModel):
    """Agent behavior configuration."""

    max_iterations: int = Field(default=3, ge=1, le=10)
    max_tests_per_file: int = Field(default=10, ge=1, le=50)
    min_confidence_score: float = Field(default=0.7, ge=0.0, le=1.0)
    include_docstrings: bool = True
    include_type_hints: bool = True


class CIConfig(BaseModel):
    """CI/CD integration configuration."""

    provider: str = Field(default="github_actions", description="CI provider: github_actions, gitlab_ci")
    output_dir: str = Field(default=".testgen", description="Output directory for CI config")
    auto_commit: bool = Field(default=False, description="Auto-commit generated tests")
    pr_comment: bool = Field(default=True, description="Post results as PR comment")


class TestGenConfig(BaseModel):
    """Top-level configuration."""

    llm: LLMConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    ci: CIConfig = Field(default_factory=CIConfig)
    target_language: str = Field(default="python")
    test_framework: str = Field(default="pytest")
    source_dirs: list[str] = Field(default=["src", "lib"])
    test_dirs: list[str] = Field(default=["tests"])

    @classmethod
    def from_file(cls, path: str | Path) -> "TestGenConfig":
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Handle LLM config specially since api_key is required
        llm_data = data.get("llm", {})
        if "api_key" not in llm_data:
            # Try env var
            api_key = os.environ.get("TESTGEN_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_data["api_key"] = api_key
            else:
                raise ValueError(
                    "LLM API key not found in config file or environment. "
                    "Set TESTGEN_LLM_API_KEY or OPENAI_API_KEY."
                )

        llm = LLMConfig(**llm_data)

        return cls(
            llm=llm,
            agent=AgentConfig(**data.get("agent", {})),
            ci=CIConfig(**data.get("ci", {})),
            target_language=data.get("target_language", "python"),
            test_framework=data.get("test_framework", "pytest"),
            source_dirs=data.get("source_dirs", ["src", "lib"]),
            test_dirs=data.get("test_dirs", ["tests"]),
        )

    @classmethod
    def from_env(cls) -> "TestGenConfig":
        """Load configuration from environment variables."""
        return cls(llm=LLMConfig.from_env())

    @classmethod
    def load(cls, path: str | Path | None = None) -> "TestGenConfig":
        """Load configuration with precedence: file > env > defaults."""
        if path:
            return cls.from_file(path)

        config_path = Path(".testgen.yaml")
        if config_path.exists():
            return cls.from_file(config_path)

        return cls.from_env()

    def to_yaml(self, path: str | Path | None = None) -> str:
        """Serialize configuration to YAML."""
        data = {
            "llm": {
                "model": self.llm.model,
                "base_url": self.llm.base_url,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
                "timeout": self.llm.timeout,
            },
            "agent": {
                "max_iterations": self.agent.max_iterations,
                "max_tests_per_file": self.agent.max_tests_per_file,
                "min_confidence_score": self.agent.min_confidence_score,
                "include_docstrings": self.agent.include_docstrings,
                "include_type_hints": self.agent.include_type_hints,
            },
            "ci": {
                "provider": self.ci.provider,
                "output_dir": self.ci.output_dir,
                "auto_commit": self.ci.auto_commit,
                "pr_comment": self.ci.pr_comment,
            },
            "target_language": self.target_language,
            "test_framework": self.test_framework,
            "source_dirs": self.source_dirs,
            "test_dirs": self.test_dirs,
        }
        yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)

        if path:
            Path(path).write_text(yaml_str)

        return yaml_str


DEFAULT_CONFIG_TEMPLATE = """\
llm:
  model: gpt-4o
  # base_url: https://api.anthropic.com/v1  # For Claude via proxy
  # api_key: Set via TESTGEN_LLM_API_KEY environment variable
  temperature: 0.2
  max_tokens: 4096
  timeout: 120

agent:
  max_iterations: 3
  max_tests_per_file: 10
  min_confidence_score: 0.7
  include_docstrings: true
  include_type_hints: true

ci:
  provider: github_actions
  output_dir: .testgen
  auto_commit: false
  pr_comment: true

target_language: python
test_framework: pytest
source_dirs:
  - src
  - lib
test_dirs:
  - tests
"""
