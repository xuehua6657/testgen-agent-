"""CI/CD integration for TestGen-Agent."""

GITHUB_ACTIONS_TEMPLATE = """\
name: Auto Test Generation

on:
  pull_request:
    branches: [main, develop]
    types: [opened, synchronize]

permissions:
  contents: write
  pull-requests: write

jobs:
  generate-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{{{ github.head_ref }}}}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install testgen-agent
        run: pip install testgen-agent

      - name: Generate tests for PR changes
        env:
          TESTGEN_LLM_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
          TESTGEN_LLM_MODEL: gpt-4o
        run: |
          testgen generate \\
            --ref origin/main \\
            --verbose

      - name: Run generated tests
        run: pytest tests/ -v --tb=short

      - name: Commit generated tests
        if: success()
        run: |
          git config user.name "testgen-bot"
          git config user.email "testgen@example.com"
          git add tests/
          git diff --staged --quiet || git commit -m "chore(testgen): auto-generate tests for PR changes"
          git push
"""

GITLAB_CI_TEMPLATE = """\
# .gitlab-ci.yml snippet for testgen-agent
# Add this to your existing .gitlab-ci.yml

testgen:
  stage: test
  image: python:3.13
  variables:
    TESTGEN_LLM_API_KEY: $OPENAI_API_KEY
    TESTGEN_LLM_MODEL: gpt-4o
  script:
    - pip install testgen-agent
    - testgen generate --ref origin/main --verbose
    - pytest tests/ -v --tb=short
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
"""

GENERIC_SCRIPT = """\
#!/bin/bash
# testgen-ci.sh - Generic CI script for testgen-agent
# Usage: ./testgen-ci.sh [base-branch]

set -e

BASE_BRANCH="${1:-main}"
REPO_PATH="${2:-.}"

echo "=== TestGen-Agent CI Runner ==="
echo "Base branch: $BASE_BRANCH"
echo "Repository: $REPO_PATH"

# Install if not already installed
if ! command -v testgen &> /dev/null; then
    echo "Installing testgen-agent..."
    pip install testgen-agent
fi

# Generate tests
echo "Generating tests for changes since $BASE_BRANCH..."
testgen generate "$REPO_PATH" --ref "origin/$BASE_BRANCH" --verbose

# Run tests
echo "Running tests..."
pytest tests/ -v --tb=short

echo "=== TestGen-Agent CI Complete ==="
"""


class CIIntegration:
    """Manage CI/CD integration for test generation."""

    def generate_workflow(self, provider: str = "github_actions") -> str:
        """Generate CI workflow configuration.

        Args:
            provider: CI provider name.

        Returns:
            Workflow configuration as string.

        Raises:
            ValueError: If provider is not supported.
        """
        templates = {
            "github_actions": GITHUB_ACTIONS_TEMPLATE,
            "gitlab_ci": GITLAB_CI_TEMPLATE,
            "generic": GENERIC_SCRIPT,
        }

        if provider not in templates:
            supported = ", ".join(templates.keys())
            raise ValueError(
                f"Unsupported CI provider: {provider}. Supported: {supported}"
            )

        return templates[provider]

    def generate_github_actions(self) -> str:
        """Generate GitHub Actions workflow YAML."""
        return self.generate_workflow("github_actions")

    def generate_gitlab_ci(self) -> str:
        """Generate GitLab CI configuration."""
        return self.generate_workflow("gitlab_ci")

    def generate_generic(self) -> str:
        """Generate a shell script wrapper for any CI."""
        return self.generate_workflow("generic")
