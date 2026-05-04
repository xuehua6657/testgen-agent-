"""Shared pytest fixtures for TestGen-Agent tests."""

import pytest


@pytest.fixture
def sample_diff():
    """Sample git diff for testing."""
    return """\
diff --git a/src/calculator.py b/src/calculator.py
index abc123..def456 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,3 +1,8 @@
 def add(a: int, b: int) -> int:
     return a + b

+def multiply(a: int, b: int) -> int:
+    \"\"\"Multiply two numbers.\"\"\"
+    return a * b
+
 def subtract(a: int, b: int) -> int:
     return a - b
"""


@pytest.fixture
def sample_source_code():
    """Sample Python source code for testing."""
    return """\
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b


def multiply(a: int, b: int) -> int:
    \"\"\"Multiply two numbers.\"\"\"
    return a * b


def subtract(a: int, b: int) -> int:
    \"\"\"Subtract b from a.\"\"\"
    return a - b


class Calculator:
    \"\"\"A simple calculator class.\"\"\"

    def __init__(self, initial: int = 0):
        self.value = initial

    def add(self, n: int) -> int:
        self.value += n
        return self.value

    def reset(self) -> None:
        self.value = 0
"""


@pytest.fixture
def sample_test_code():
    """Sample valid test code for testing."""
    return """\
import pytest

def test_add():
    assert add(1, 2) == 3


def test_add_negative():
    assert add(-1, -1) == -2


def test_multiply():
    assert multiply(3, 4) == 12


def test_multiply_zero():
    assert multiply(5, 0) == 0
"""


@pytest.fixture
def sample_invalid_code():
    """Sample invalid Python code for testing."""
    return """\
def test_broken(
    syntax error here
    assert
"""
