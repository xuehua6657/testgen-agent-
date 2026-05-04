"""Tests for TestGen-Agent utility functions."""

import tempfile
from pathlib import Path

import pytest

from testgen.utils import (
    detect_language,
    extract_code_blocks,
    find_test_file,
    read_file,
    safe_write_file,
)


class TestDetectLanguage:
    @pytest.mark.parametrize(
        "file_path,expected",
        [
            ("src/example.py", "python"),
            ("lib/utils.js", "javascript"),
            ("app/component.tsx", "typescript"),
            ("main.go", "go"),
            ("lib.rs", "rust"),
            ("unknown.xyz", "unknown"),
        ],
    )
    def test_detect_language(self, file_path, expected):
        assert detect_language(file_path) == expected


class TestExtractCodeBlocks:
    def test_python_fence(self):
        text = "Here is the code:\n```python\ndef test():\n    pass\n```\nDone."
        blocks = extract_code_blocks(text, "python")
        assert len(blocks) == 1
        assert "def test():" in blocks[0]

    def test_generic_fence(self):
        text = "```\ndef test():\n    pass\n```"
        blocks = extract_code_blocks(text, "python")
        assert len(blocks) == 1
        assert "def test():" in blocks[0]

    def test_no_fence(self):
        text = "def test():\n    pass"
        blocks = extract_code_blocks(text, "python")
        assert len(blocks) == 1
        assert blocks[0] == text

    def test_empty(self):
        blocks = extract_code_blocks("", "python")
        assert blocks == []

    def test_multiple_blocks(self):
        text = "```python\ndef a(): pass\n```\n\n```python\ndef b(): pass\n```"
        blocks = extract_code_blocks(text, "python")
        assert len(blocks) == 2
        assert "def a():" in blocks[0]
        assert "def b():" in blocks[1]


class TestReadFile:
    def test_read_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            content = read_file(f.name)
            assert content == "hello world"

    def test_read_nonexistent_file(self):
        content = read_file("/nonexistent/file.txt")
        assert content == ""


class TestSafeWriteFile:
    def test_write_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            assert safe_write_file(path, "content") is True
            assert path.read_text() == "content"

    def test_write_nested_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "test.txt"
            assert safe_write_file(path, "nested") is True
            assert path.read_text() == "nested"

    def test_append_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            safe_write_file(path, "line1\n")
            safe_write_file(path, "line2\n", append=True)
            assert path.read_text() == "line1\nline2\n"


class TestFindTestFile:
    def test_find_test_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directory structure
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            (test_dir / "test_example.py").write_text("# test")

            result = find_test_file("src/example.py", ["tests"], base_dir=tmpdir)
            assert result is not None
            assert "test_example.py" in result

    def test_find_test_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            (test_dir / "example_test.py").write_text("# test")

            result = find_test_file("src/example.py", ["tests"], base_dir=tmpdir)
            assert result is not None
            assert "example_test.py" in result

    def test_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_test_file("src/example.py", ["tests"], base_dir=tmpdir)
            assert result is None
