"""Tests for tolerance-based comparison logic.

Covers:
- Absolute-only tolerance pass/fail
- Relative-only tolerance pass/fail
- Combined absolute + relative with OR logic
- Edge case: expected=0 with absolute tolerance (no division by zero)
- Edge case: expected=0 with relative tolerance (fallback to absolute)
- ComparisonResult immutability (frozen dataclass)
"""

import pytest

from stockvaluefinder.validation.comparators import (
    ComparisonResult,
    compare_within_tolerance,
)
from stockvaluefinder.validation.schema import Tolerance


class TestCompareWithinToleranceAbsolute:
    """Absolute-only tolerance checks."""

    def test_absolute_pass_within_tolerance(self) -> None:
        """Test 1: delta 0.5 <= absolute 1.0 => pass."""
        tolerance = Tolerance(absolute=1.0)
        result = compare_within_tolerance(100.0, 100.5, tolerance)
        assert result.passed is True
        assert result.delta == pytest.approx(0.5)

    def test_absolute_fail_exceeds_tolerance(self) -> None:
        """Test 2: delta 2.0 > absolute 1.0 => fail."""
        tolerance = Tolerance(absolute=1.0)
        result = compare_within_tolerance(100.0, 102.0, tolerance)
        assert result.passed is False
        assert result.delta == pytest.approx(2.0)

    def test_absolute_exact_boundary(self) -> None:
        """delta == absolute tolerance => pass (inclusive)."""
        tolerance = Tolerance(absolute=1.0)
        result = compare_within_tolerance(100.0, 101.0, tolerance)
        assert result.passed is True
        assert result.delta == pytest.approx(1.0)


class TestCompareWithinToleranceRelative:
    """Relative-only tolerance checks."""

    def test_relative_pass(self) -> None:
        """Test 3: 0.5% relative delta < 1% relative tolerance => pass."""
        tolerance = Tolerance(relative=0.01)
        result = compare_within_tolerance(100.0, 100.5, tolerance)
        assert result.passed is True

    def test_relative_fail(self) -> None:
        """Test 4: 2% relative delta > 1% relative tolerance => fail."""
        tolerance = Tolerance(relative=0.01)
        result = compare_within_tolerance(100.0, 102.0, tolerance)
        assert result.passed is False

    def test_relative_exact_boundary(self) -> None:
        """Relative delta == relative tolerance => pass (inclusive)."""
        tolerance = Tolerance(relative=0.01)
        result = compare_within_tolerance(100.0, 101.0, tolerance)
        assert result.passed is True


class TestCompareWithinToleranceBoth:
    """Combined absolute + relative tolerance (OR logic)."""

    def test_both_passes_if_either_passes(self) -> None:
        """Test 5: passes if EITHER absolute OR relative is satisfied."""
        # absolute=0.1 (too tight for delta=1.0), relative=0.02 (passes: 1% < 2%)
        tolerance = Tolerance(absolute=0.1, relative=0.02)
        result = compare_within_tolerance(100.0, 101.0, tolerance)
        assert result.passed is True

    def test_both_fails_if_neither_passes(self) -> None:
        """Fails if neither absolute nor relative is satisfied."""
        tolerance = Tolerance(absolute=0.1, relative=0.001)
        result = compare_within_tolerance(100.0, 105.0, tolerance)
        assert result.passed is False

    def test_both_absolute_pass_relative_fail(self) -> None:
        """Passes when absolute passes but relative does not."""
        tolerance = Tolerance(absolute=2.0, relative=0.001)
        result = compare_within_tolerance(100.0, 101.0, tolerance)
        assert result.passed is True


class TestCompareWithinToleranceEdgeCases:
    """Edge cases for tolerance comparison."""

    def test_expected_zero_with_absolute(self) -> None:
        """Test 6: expected=0 with absolute tolerance, no division by zero."""
        tolerance = Tolerance(absolute=0.5)
        result = compare_within_tolerance(0.0, 0.3, tolerance)
        assert result.passed is True
        assert result.delta == pytest.approx(0.3)

    def test_expected_zero_with_relative(self) -> None:
        """Test 7: expected=0 with relative tolerance, falls back gracefully."""
        tolerance = Tolerance(relative=0.5)
        result = compare_within_tolerance(0.0, 0.3, tolerance)
        # When expected=0 and only relative is set, fall back: delta <= relative
        assert result.passed is True

    def test_expected_zero_both_tolerances(self) -> None:
        """expected=0 with both tolerances uses absolute check."""
        tolerance = Tolerance(absolute=0.5, relative=0.01)
        result = compare_within_tolerance(0.0, 0.3, tolerance)
        assert result.passed is True

    def test_negative_values(self) -> None:
        """Negative expected/computed values work correctly."""
        tolerance = Tolerance(absolute=0.1)
        result = compare_within_tolerance(-2.5, -2.52, tolerance)
        assert result.passed is True
        assert result.delta == pytest.approx(0.02)

    def test_both_zero(self) -> None:
        """expected=0 and computed=0 passes with any tolerance."""
        tolerance = Tolerance(absolute=0.01)
        result = compare_within_tolerance(0.0, 0.0, tolerance)
        assert result.passed is True
        assert result.delta == pytest.approx(0.0)


class TestComparisonResultFrozen:
    """Test 13: ComparisonResult is frozen/immutable."""

    def test_comparison_result_is_frozen(self) -> None:
        """ComparisonResult attributes cannot be reassigned."""
        result = ComparisonResult(
            metric_name="test",
            expected=100.0,
            computed=100.5,
            delta=0.5,
            tolerance_applied=Tolerance(absolute=1.0),
            passed=True,
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]

    def test_comparison_result_fields(self) -> None:
        """ComparisonResult has all required fields."""
        tolerance = Tolerance(absolute=1.0)
        result = ComparisonResult(
            metric_name="m_score",
            expected=-2.5,
            computed=-2.52,
            delta=0.02,
            tolerance_applied=tolerance,
            passed=True,
        )
        assert result.metric_name == "m_score"
        assert result.expected == pytest.approx(-2.5)
        assert result.computed == pytest.approx(-2.52)
        assert result.delta == pytest.approx(0.02)
        assert result.tolerance_applied == tolerance
        assert result.passed is True
