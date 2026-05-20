"""Tolerance-based comparison utilities for metric validation.

Provides the ``ComparisonResult`` frozen dataclass and the
``compare_within_tolerance()`` pure function used by
``MetricRegistry.check()`` and downstream golden tests.

Usage::

    from stockvaluefinder.validation.comparators import compare_within_tolerance
    from stockvaluefinder.validation.schema import Tolerance

    tol = Tolerance(absolute=0.05)
    result = compare_within_tolerance(-2.5, -2.52, tol)
    print(result.passed, result.delta)
"""

from __future__ import annotations

from dataclasses import dataclass

from stockvaluefinder.validation.schema import Tolerance


@dataclass(frozen=True)
class ComparisonResult:
    """Immutable result of comparing expected vs computed against tolerance.

    Attributes:
        metric_name: Name of the metric being compared.
        expected: Reference/expected value.
        computed: Actually computed value.
        delta: Absolute difference ``abs(computed - expected)``.
        tolerance_applied: The tolerance specification used for this check.
        passed: Whether the computed value is within tolerance.
    """

    metric_name: str
    expected: float
    computed: float
    delta: float
    tolerance_applied: Tolerance
    passed: bool


def compare_within_tolerance(
    expected: float,
    computed: float,
    tolerance: Tolerance,
) -> ComparisonResult:
    """Check whether *computed* is within *tolerance* of *expected*.

    If both ``absolute`` and ``relative`` tolerances are specified, the value
    passes if **either** tolerance is satisfied (OR logic, not AND).

    Edge cases:
        - When ``expected == 0`` and ``relative`` is set, falls back to
          comparing ``delta <= relative`` to avoid division by zero.
        - When ``expected == 0`` and ``absolute`` is set, the absolute
          check is used directly.

    Args:
        expected: Reference/expected value.
        computed: Actually computed value.
        tolerance: Tolerance specification.

    Returns:
        ``ComparisonResult`` with pass/fail status, delta, and applied tolerance.
    """
    delta = abs(computed - expected)

    passed = False

    # Absolute tolerance check
    if tolerance.absolute is not None and delta <= tolerance.absolute:
        passed = True

    # Relative tolerance check (OR with absolute)
    if tolerance.relative is not None:
        if expected == 0.0:
            # Avoid division by zero: compare delta directly to relative value
            if delta <= tolerance.relative:
                passed = True
        else:
            relative_delta = delta / abs(expected)
            if relative_delta <= tolerance.relative:
                passed = True

    return ComparisonResult(
        metric_name="",
        expected=expected,
        computed=computed,
        delta=delta,
        tolerance_applied=tolerance,
        passed=passed,
    )
