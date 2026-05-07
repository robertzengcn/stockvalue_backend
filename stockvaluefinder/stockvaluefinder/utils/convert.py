"""Type conversion utilities.

Provides safe conversion functions for handling None, NaN, and other
edge cases when converting financial data values to float.
"""

from typing import Any


def to_float(value: Any, field_name: str = "") -> float:
    """Convert a value to float, treating nan/None/empty as 0.0.

    Args:
        value: Value to convert (may be None, NaN, string, int, float, etc.).
        field_name: Optional field name for debugging context.

    Returns:
        Float value, or 0.0 if the input is None, NaN, or unconvertible.

    Examples:
        >>> to_float(42)
        42.0
        >>> to_float(None)
        0.0
        >>> to_float(float('nan'))
        0.0
        >>> to_float("abc")
        0.0
    """
    if value is None:
        return 0.0
    try:
        result = float(value)
        if result != result:  # NaN check
            return 0.0
        return result
    except (ValueError, TypeError):
        return 0.0
