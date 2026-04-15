"""Unit tests for validators module."""

import pytest
from decimal import Decimal

from stockvaluefinder.models.enums import Market
from stockvaluefinder.utils.validators import (
    validate_ticker_format,
    validate_market_enum,
    validate_positive_decimal,
    validate_percentage,
    validate_chinese_name,
    validate_rate,
)


class TestValidateTickerFormat:
    """Tests for validate_ticker_format function."""

    def test_normalizes_lowercase_to_uppercase(self) -> None:
        """validate_ticker_format should normalize lowercase SH to uppercase."""
        assert validate_ticker_format("600519.sh") == "600519.SH"

    def test_already_uppercase_passthrough(self) -> None:
        """validate_ticker_format should accept already-uppercase ticker."""
        assert validate_ticker_format("600519.SH") == "600519.SH"

    def test_shenzhen_market_valid(self) -> None:
        """validate_ticker_format should accept SZ market ticker."""
        assert validate_ticker_format("000002.SZ") == "000002.SZ"

    def test_hk_market_valid(self) -> None:
        """validate_ticker_format should accept HK market ticker (6-digit format)."""
        assert validate_ticker_format("000700.HK") == "000700.HK"

    def test_invalid_format_raises_value_error(self) -> None:
        """validate_ticker_format should raise ValueError for non-matching format."""
        with pytest.raises(ValueError, match="Invalid ticker format"):
            validate_ticker_format("INVALID")

    def test_five_digits_raises_value_error(self) -> None:
        """validate_ticker_format should raise ValueError for 5-digit ticker."""
        with pytest.raises(ValueError, match="Invalid ticker format"):
            validate_ticker_format("12345.SH")

    def test_invalid_market_suffix_raises_value_error(self) -> None:
        """validate_ticker_format should raise ValueError for unsupported market."""
        with pytest.raises(ValueError, match="Invalid ticker format"):
            validate_ticker_format("600519.XX")


class TestValidateMarketEnum:
    """Tests for validate_market_enum function."""

    def test_string_a_share_returns_enum(self) -> None:
        """validate_market_enum should convert string 'A_SHARE' to Market enum."""
        assert validate_market_enum("A_SHARE") == Market.A_SHARE

    def test_enum_passthrough(self) -> None:
        """validate_market_enum should return the same Market enum object."""
        result = validate_market_enum(Market.HK_SHARE)
        assert result is Market.HK_SHARE

    def test_invalid_string_raises_value_error(self) -> None:
        """validate_market_enum should raise ValueError for invalid string."""
        with pytest.raises(ValueError, match="Invalid market"):
            validate_market_enum("INVALID")

    def test_case_sensitive_raises_value_error(self) -> None:
        """validate_market_enum should be case-sensitive."""
        with pytest.raises(ValueError, match="Invalid market"):
            validate_market_enum("a_share")


class TestValidatePositiveDecimal:
    """Tests for validate_positive_decimal function."""

    def test_valid_float_returns_decimal(self) -> None:
        """validate_positive_decimal should convert float to Decimal."""
        assert validate_positive_decimal(1.5) == Decimal("1.5")

    def test_zero_is_accepted(self) -> None:
        """validate_positive_decimal should accept zero (>= 0)."""
        assert validate_positive_decimal(0) == Decimal("0")

    def test_negative_raises_value_error(self) -> None:
        """validate_positive_decimal should reject negative values."""
        with pytest.raises(ValueError, match="must be positive"):
            validate_positive_decimal(-1.0)

    def test_non_numeric_string_raises_value_error(self) -> None:
        """validate_positive_decimal should reject non-numeric strings."""
        with pytest.raises(ValueError, match="valid number"):
            validate_positive_decimal("abc")

    def test_decimal_input_returns_decimal(self) -> None:
        """validate_positive_decimal should accept Decimal input."""
        result = validate_positive_decimal(Decimal("3.14"))
        assert result == Decimal("3.14")


class TestValidatePercentage:
    """Tests for validate_percentage function."""

    def test_valid_percentage_within_range(self) -> None:
        """validate_percentage should accept value within 0-1 range."""
        assert validate_percentage(0.05) == Decimal("0.05")

    def test_above_max_raises_value_error(self) -> None:
        """validate_percentage should reject value above max (1.0)."""
        with pytest.raises(ValueError):
            validate_percentage(1.5)

    def test_below_min_raises_value_error(self) -> None:
        """validate_percentage should reject value below min (0.0)."""
        with pytest.raises(ValueError):
            validate_percentage(-0.1)

    def test_custom_min_max_boundary(self) -> None:
        """validate_percentage should accept value at custom boundary."""
        assert validate_percentage(0.5, min_value=0.0, max_value=0.5) == Decimal("0.5")

    def test_string_input_accepted(self) -> None:
        """validate_percentage should accept string input."""
        assert validate_percentage("0.25") == Decimal("0.25")


class TestValidateChineseName:
    """Tests for validate_chinese_name function."""

    def test_chinese_characters_accepted(self) -> None:
        """validate_chinese_name should accept Chinese characters."""
        assert validate_chinese_name("贵州茅台") == "贵州茅台"

    def test_english_name_accepted(self) -> None:
        """validate_chinese_name should accept English names."""
        assert validate_chinese_name("ABC Corp") == "ABC Corp"

    def test_empty_string_raises_value_error(self) -> None:
        """validate_chinese_name should reject empty strings."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_chinese_name("")

    def test_special_characters_raises_value_error(self) -> None:
        """validate_chinese_name should reject names with special characters."""
        with pytest.raises(ValueError, match="Invalid name"):
            validate_chinese_name("test@#$")

    def test_whitespace_stripped(self) -> None:
        """validate_chinese_name should strip leading/trailing whitespace."""
        assert validate_chinese_name("  贵州茅台  ") == "贵州茅台"


class TestValidateRate:
    """Tests for validate_rate function."""

    def test_valid_rate_within_range(self) -> None:
        """validate_rate should accept rate within 0-20% range."""
        assert validate_rate(0.0235) == Decimal("0.0235")

    def test_above_20_percent_raises_value_error(self) -> None:
        """validate_rate should reject rates above 20%."""
        with pytest.raises(ValueError):
            validate_rate(0.25)

    def test_zero_accepted(self) -> None:
        """validate_rate should accept zero rate."""
        assert validate_rate(0) == Decimal("0")
