"""A simple calculator module for demonstrating testgen-agent."""


def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Sum of a and b.
    """
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a.

    Args:
        a: First number.
        b: Number to subtract.

    Returns:
        Difference of a and b.
    """
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Product of a and b.
    """
    return a * b


def divide(a: int, b: int) -> float:
    """Divide a by b.

    Args:
        a: Dividend.
        b: Divisor.

    Returns:
        Quotient of a and b.

    Raises:
        ValueError: If b is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


class Calculator:
    """A simple calculator that maintains state."""

    def __init__(self, initial: int = 0):
        """Initialize calculator with optional starting value.

        Args:
            initial: Starting value (default 0).
        """
        self.value = initial

    def add(self, n: int) -> int:
        """Add n to current value."""
        self.value += n
        return self.value

    def subtract(self, n: int) -> int:
        """Subtract n from current value."""
        self.value -= n
        return self.value

    def multiply(self, n: int) -> int:
        """Multiply current value by n."""
        self.value *= n
        return self.value

    def reset(self) -> None:
        """Reset value to zero."""
        self.value = 0
