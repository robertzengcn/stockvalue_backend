"""Custom Pydantic validators for StockValueFinder domain."""

import re
from decimal import Decimal


from stockvaluefinder.models.enums import Market


def validate_ticker_format(ticker: str) -> str:
    """Validate and normalize ticker format.

    Ticker must match pattern: \d{6}\.(SH|SZ|HK)
    Examples: '600519.SH', '000002.SZ', '0700.HK'

    Args:
        ticker: Stock ticker symbol

    Returns:
        Normalized ticker (uppercase)

    Raises:
        ValueError: If ticker format is invalid
    """
    pattern = re.compile(r"^\d{6}\.(SH|SZ|HK)$", re.IGNORECASE)
    if not pattern.match(ticker):
        raise ValueError(
            f"Invalid ticker format '{ticker}'. Expected format: "
            r"6-digit number followed by '.SH', '.SZ', or '.HK' (e.g., '600519.SH')"
        )
    return ticker.upper()


def validate_market_enum(market: str | Market) -> Market:
    """Validate market enum value.

    Args:
        market: Market value (string or Market enum)

    Returns:
        Market enum value

    Raises:
        ValueError: If market is not valid
    """
    if isinstance(market, Market):
        return market

    try:
        return Market(market)
    except ValueError:
        valid_values = [m.value for m in Market]
        raise ValueError(
            f"Invalid market '{market}'. Must be one of: {valid_values}"
        ) from None


def validate_positive_decimal(
    value: float | Decimal | str,
    field_name: str = "value",
) -> Decimal:
    """Validate that a value is a positive decimal.

    Args:
        value: Value to validate
        field_name: Name of the field for error message

    Returns:
        Decimal value

    Raises:
        ValueError: If value is not positive
    """
    try:
        decimal_value = Decimal(str(value))
    except (ValueError, TypeError) as e:
        raise ValueError(f"{field_name} must be a valid number") from e

    if decimal_value < 0:
        raise ValueError(f"{field_name} must be positive (got {value})")

    return decimal_value


def validate_percentage(
    value: float | Decimal | str,
    field_name: str = "value",
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> Decimal:
    """Validate that a value is a percentage within range.

    Args:
        value: Value to validate (as decimal, e.g., 0.05 for 5%)
        field_name: Name of the field for error message
        min_value: Minimum allowed value (default 0.0)
        max_value: Maximum allowed value (default 1.0 = 100%)

    Returns:
        Decimal value

    Raises:
        ValueError: If value is outside valid range
    """
    try:
        decimal_value = Decimal(str(value))
    except (ValueError, TypeError) as e:
        raise ValueError(f"{field_name} must be a valid number") from e

    if decimal_value < Decimal(str(min_value)) or decimal_value > Decimal(
        str(max_value)
    ):
        raise ValueError(
            f"{field_name} must be between {min_value:.0%} and {max_value:.0%} "
            f"(got {float(decimal_value):.2%})"
        )

    return decimal_value


def validate_chinese_name(name: str) -> str:
    """Validate that a name contains valid characters (Chinese, English, numbers).

    Args:
        name: Company or stock name

    Returns:
        Validated name (stripped of leading/trailing whitespace)

    Raises:
        ValueError: If name is empty or contains invalid characters
    """
    if not name or not name.strip():
        raise ValueError("Name cannot be empty")

    stripped_name = name.strip()

    # Allow Chinese characters, English letters, numbers, common punctuation
    # \u4e00-\u9fff: CJK Unified Ideographs
    # \u3400-\u4dbf: CJK Unified Ideographs Extension A
    # \uf900-\ufaff: CJK Compatibility Ideographs
    pattern = re.compile(
        r"^[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaffa-zA-Z0-9\s\(\)\（\）\-\.]+$"
    )

    if not pattern.match(stripped_name):
        raise ValueError(
            f"Invalid name '{name}'. Must contain only Chinese characters, "
            "English letters, numbers, and common punctuation"
        )

    return stripped_name


def validate_rate(value: float | Decimal | str, field_name: str = "rate") -> Decimal:
    """Validate that an interest rate is within valid range (0-20%).

    Args:
        value: Rate value as decimal (e.g., 0.0235 for 2.35%)
        field_name: Name of the field for error message

    Returns:
        Decimal value

    Raises:
        ValueError: If rate is outside valid range
    """
    return validate_percentage(
        value,
        field_name=field_name,
        min_value=0.0,
        max_value=0.20,  # 20%
    )
