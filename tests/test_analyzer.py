"""Tests for TestGen-Agent code analyzer."""

import tempfile
from pathlib import Path

from testgen.analyzer import CodeAnalyzer
from testgen.config import TestGenConfig
from testgen.models import CodeChange


SAMPLE_DIFF = """\
diff --git a/src/calculator.py b/src/calculator.py
index abc123..def456 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,5 +1,10 @@
 def add(a: int, b: int) -> int:
+    \"\"\"Add two numbers.\"\"\"
     return a + b

+def multiply(a: int, b: int) -> int:
+    \"\"\"Multiply two numbers.\"\"\"
+    return a * b
+
 def subtract(a: int, b: int) -> int:
     return a - b
"""


def make_config():
    """Create a TestGenConfig for testing."""
    return TestGenConfig(
        llm={
            "api_key": "test-key-123",
            "model": "gpt-4o",
        }
    )


class TestCodeAnalyzer:
    def setup_method(self):
        self.config = TestGenConfig(
            llm={
                "api_key": "test-key-123",
                "model": "gpt-4o",
            }
        )
        self.analyzer = CodeAnalyzer(self.config)

    def test_parse_diff_single_file(self):
        changes = self.analyzer.parse_diff(SAMPLE_DIFF)

        assert len(changes) == 1
        change = changes[0]
        assert change.file_path == "src/calculator.py"
        assert change.language == "python"
        assert len(change.added_lines) > 0

    def test_parse_diff_empty(self):
        changes = self.analyzer.parse_diff("")
        assert changes == []

    def test_parse_diff_multiple_files(self):
        diff = """\
diff --git a/src/a.py b/src/a.py
index abc..def 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-old
+new

diff --git a/src/b.py b/src/b.py
index abc..def 100644
--- a/src/b.py
+++ b/src/b.py
@@ -1 +1 @@
-old
+new
"""
        changes = self.analyzer.parse_diff(diff)
        assert len(changes) == 2
        assert changes[0].file_path == "src/a.py"
        assert changes[1].file_path == "src/b.py"

    def test_extract_changed_functions(self):
        diff_text = """\
+def hello():
+    pass
+
+def world(name: str):
+    return f"Hello {name}"
"""
        functions = self.analyzer._extract_changed_functions(diff_text, "python")
        assert "hello" in functions
        assert "world" in functions

    def test_assess_risk_low(self):
        changes = [
            CodeChange(
                file_path="src/a.py",
                diff_text="+line",
                added_lines=[1, 2],
                removed_lines=[],
                changed_functions=["func"],
                language="python",
            ),
        ]
        risk = self.analyzer.assess_risk(changes)
        assert risk == "low"

    def test_assess_risk_medium(self):
        changes = [
            CodeChange(
                file_path=f"src/file{i}.py",
                diff_text="+line",
                added_lines=list(range(20)),
                removed_lines=[],
                changed_functions=[f"func{i}"],
                language="python",
            )
            for i in range(5)
        ]
        risk = self.analyzer.assess_risk(changes)
        assert risk == "medium"

    def test_assess_risk_high(self):
        changes = [
            CodeChange(
                file_path=f"src/file{i}.py",
                diff_text="+line",
                added_lines=list(range(60)),
                removed_lines=[],
                changed_functions=[f"func{i}"],
                language="python",
            )
            for i in range(12)
        ]
        risk = self.analyzer.assess_risk(changes)
        assert risk == "high"

    def test_analyze_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "calculator.py").write_text("""\
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
""")

            # Create test file
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            (test_dir / "test_calculator.py").write_text("""\
def test_add():
    assert add(1, 2) == 3
""")

            change = CodeChange(
                file_path="src/calculator.py",
                diff_text="+def multiply",
                added_lines=[5],
                removed_lines=[],
                changed_functions=["multiply"],
                language="python",
            )

            context = self.analyzer.analyze_context(change, tmpdir)

            assert "def add" in context["source_code"]
            assert "def test_add" in context["existing_tests"]

    def test_run_full_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "calculator.py").write_text("def add(a, b): return a + b")

            result = self.analyzer.run(SAMPLE_DIFF, tmpdir)

            assert len(result.changes) == 1
            assert result.risk_level == "low"
            assert "src/calculator.py" in result.affected_modules
            assert "Found 1 changed files" in result.summary

    def test_run_no_changes(self):
        result = self.analyzer.run("", ".")

        assert result.changes == []
        assert result.risk_level == "low"
        assert "No code changes" in result.summary
