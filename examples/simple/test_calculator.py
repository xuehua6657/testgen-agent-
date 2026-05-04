"""Example tests for the calculator module."""

import pytest

from calculator import Calculator, add, divide, multiply, subtract


class TestAdd:
    def test_add_positive(self):
        assert add(1, 2) == 3

    def test_add_negative(self):
        assert add(-1, -1) == -2

    def test_add_zero(self):
        assert add(0, 0) == 0


class TestSubtract:
    def test_subtract_positive(self):
        assert subtract(5, 3) == 2

    def test_subtract_negative_result(self):
        assert subtract(3, 5) == -2


class TestMultiply:
    def test_multiply_positive(self):
        assert multiply(3, 4) == 12

    def test_multiply_by_zero(self):
        assert multiply(5, 0) == 0


class TestDivide:
    def test_divide_positive(self):
        assert divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)


class TestCalculator:
    def test_initial_value(self):
        calc = Calculator(10)
        assert calc.value == 10

    def test_default_initial(self):
        calc = Calculator()
        assert calc.value == 0

    def test_add(self):
        calc = Calculator(5)
        calc.add(3)
        assert calc.value == 8

    def test_reset(self):
        calc = Calculator(100)
        calc.reset()
        assert calc.value == 0
