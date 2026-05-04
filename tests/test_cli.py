"""Tests for TestGen-Agent CLI."""

import pytest
from typer.testing import CliRunner

from testgen.cli import app


runner = CliRunner()


class TestCLI:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "testgen-agent v" in result.output

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "testgen" in result.output.lower()
        assert "generate" in result.output.lower()

    def test_generate_help(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--ref" in result.output
        assert "--config" in result.output

    def test_validate_help(self):
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output

    def test_ci_setup_help(self):
        result = runner.invoke(app, ["ci-setup", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output

    def test_config_init_help(self):
        result = runner.invoke(app, ["config-init", "--help"])
        assert result.exit_code == 0

    def test_generate_not_git_repo(self):
        result = runner.invoke(app, ["generate", "/tmp"])
        # Should fail because /tmp is not a git repo
        assert result.exit_code != 0 or "not a git repository" in result.output

    def test_generate_no_api_key(self, monkeypatch, tmp_path):
        # Create a git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Remove API key
        monkeypatch.delenv("TESTGEN_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = runner.invoke(app, ["generate", str(tmp_path)])
        assert result.exit_code != 0
        assert "API key" in result.output.lower() or "Error" in result.output
