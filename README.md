# TestGen-Agent

AI-powered automated test generation from code changes.

## Overview

TestGen-Agent analyzes git diffs, uses an LLM-powered agent to understand code changes, and automatically generates comprehensive unit tests. It integrates with CI pipelines for a closed loop from code change to test verification.

## Features

- **Smart Code Analysis**: Parses git diffs to identify changed functions and modules
- **AI-Powered Generation**: Uses LLM to generate pytest-compatible unit tests
- **Multi-Tier Validation**: Syntax check, import validation, dry-run collection, and LLM quality scoring
- **LangGraph Workflow**: State machine with automatic retry on failure
- **CI Integration**: GitHub Actions, GitLab CI, and generic shell script support
- **CLI Tool**: Simple command-line interface with rich output

## Installation

```bash
pip install testgen-agent
```

Or from source:

```bash
git clone https://github.com/YOUR_USERNAME/testgen-agent.git
cd testgen-agent
pip install -e ".[dev]"
```

## Quick Start

### 1. Set up API key

```bash
export TESTGEN_LLM_API_KEY="your-api-key"
```

Works with OpenAI, Anthropic (via proxy), Ollama, and any OpenAI-compatible API.

### 2. Initialize config (optional)

```bash
testgen config init
```

This creates a `.testgen.yaml` with sensible defaults.

### 3. Generate tests

```bash
cd your-project
testgen generate --ref HEAD~1
```

### 4. Validate existing tests

```bash
testgen validate tests/test_example.py --source src/example.py
```

## CLI Commands

| Command | Description |
|---|---|
| `testgen generate [repo]` | Analyze code changes and generate unit tests |
| `testgen validate <test_file>` | Validate existing tests for quality |
| `testgen ci-setup` | Generate CI pipeline configuration |
| `testgen config init` | Create default configuration file |
| `testgen version` | Show version |

## Configuration

Create a `.testgen.yaml` file:

```yaml
llm:
  model: gpt-4o
  temperature: 0.2
  max_tokens: 4096

agent:
  max_iterations: 3
  max_tests_per_file: 10
  min_confidence_score: 0.7

ci:
  provider: github_actions
  auto_commit: false
  pr_comment: true

target_language: python
test_framework: pytest
source_dirs:
  - src
test_dirs:
  - tests
```

Or use environment variables:

```bash
export TESTGEN_LLM_API_KEY="your-key"
export TESTGEN_LLM_MODEL="gpt-4o"
export TESTGEN_LLM_BASE_URL=""  # For non-OpenAI providers
```

## CI Integration

Generate CI workflow configuration:

```bash
testgen ci-setup --provider github_actions
```

This creates `.github/workflows/testgen.yml` that:
- Triggers on PR to main/develop
- Runs testgen on changed files
- Commits generated tests to the PR branch

## Architecture

```
START -> [analyze] -> [specify_tests] -> [generate] -> [validate]
                                                        |
                    +-----> [retry] (if failed, iteration < max)
                    +-----> [save] (if valid tests) -> END
                    +-----> [end] (if all fail) -> END
```

### Components

| Module | Purpose |
|---|---|
| `analyzer` | Git diff parsing and code structure analysis |
| `generator` | LLM interface with retry logic |
| `validator` | Multi-tier test validation pipeline |
| `agent` | LangGraph workflow orchestration |
| `cli` | Typer-based CLI interface |
| `ci` | CI/CD configuration generation |

## Supported LLM Providers

TestGen-Agent uses the `openai` package, making it compatible with any OpenAI-compatible API:

| Provider | Configuration |
|---|---|
| OpenAI | Default (no base_url needed) |
| Anthropic Claude | `base_url: https://api.anthropic.com/v1` (via proxy) |
| Ollama | `base_url: http://localhost:11434/v1` |
| Azure OpenAI | `base_url: https://<resource>.openai.azure.com/` |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/testgen/ --cov-report=html

# Lint
ruff check src/ tests/

# Type check
mypy src/testgen/
```

## License

MIT
