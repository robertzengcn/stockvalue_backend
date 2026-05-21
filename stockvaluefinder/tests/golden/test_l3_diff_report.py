"""L3 diff report generation utilities and tests.

Provides helper functions for converting ComparisonResult lists into
structured diff reports, human-readable tables, JSON strings, and
pass-rate summaries.  These utilities are used by L3 golden tests to
diagnose failures with structured output.

Functions:
    generate_diff_report: Convert ComparisonResult list to list of dicts.
    format_diff_table: Format diff report as aligned table string.
    diff_report_to_json: Serialize diff report to JSON.
    summarize_pass_rates: Calculate P0/P1 pass rates from diff report.

Tests:
    TestL3DiffReport: 5 test methods verifying all helper functions.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from stockvaluefinder.validation.comparators import ComparisonResult
from stockvaluefinder.validation.schema import MetricRegistry, Tolerance


# ---------------------------------------------------------------------------
# Helper functions (test utilities, not production code)
# ---------------------------------------------------------------------------


def generate_diff_report(
    comparisons: list[ComparisonResult],
) -> list[dict[str, Any]]:
    """Convert ComparisonResult list to structured diff report.

    Each entry contains: metric_name, expected, computed, delta,
    tolerance (dict with only non-None keys), and passed boolean.

    Args:
        comparisons: List of ComparisonResult objects from registry.check().

    Returns:
        List of dicts suitable for JSON serialization or table formatting.

    Example::

        >>> tol = Tolerance(absolute=0.05)
        >>> cmp = ComparisonResult("m_score", -0.74, -0.75, 0.01, tol, True)
        >>> report = generate_diff_report([cmp])
        >>> report[0]["metric_name"]
        'm_score'
    """
    report: list[dict[str, Any]] = []
    for cmp in comparisons:
        tol_dict: dict[str, float] = {}
        if cmp.tolerance_applied.absolute is not None:
            tol_dict["absolute"] = cmp.tolerance_applied.absolute
        if cmp.tolerance_applied.relative is not None:
            tol_dict["relative"] = cmp.tolerance_applied.relative
        report.append(
            {
                "metric_name": cmp.metric_name,
                "expected": cmp.expected,
                "computed": cmp.computed,
                "delta": cmp.delta,
                "tolerance": tol_dict,
                "passed": cmp.passed,
            }
        )
    return report


def format_diff_table(report: list[dict[str, Any]]) -> str:
    """Format diff report as human-readable aligned table string.

    Columns: METRIC (20), EXPECTED (12), COMPUTED (12), DELTA (12),
    TOLERANCE (20), STATUS (6).  Passing entries show "PASS", failing
    entries show "FAIL".

    Args:
        report: List of diff entry dicts from generate_diff_report.

    Returns:
        Multi-line string with header, separator, and one row per metric.

    Example::

        >>> entry = {"metric_name": "x", "expected": 1.0, "computed": 1.0,
        ...          "delta": 0.0, "tolerance": {"absolute": 0.05}, "passed": True}
        >>> "PASS" in format_diff_table([entry])
        True
    """
    header = (
        f"{'METRIC':<20} {'EXPECTED':>12} {'COMPUTED':>12} "
        f"{'DELTA':>12} {'TOLERANCE':>20} {'STATUS':>6}"
    )
    separator = "-" * len(header)
    lines = [header, separator]
    for entry in report:
        tol_str = ", ".join(f"{k}={v}" for k, v in entry["tolerance"].items())
        status = "PASS" if entry["passed"] else "FAIL"
        lines.append(
            f"{entry['metric_name']:<20} {entry['expected']:>12.6f} "
            f"{entry['computed']:>12.6f} {entry['delta']:>12.6f} "
            f"{tol_str:<20} {status:>6}"
        )
    return "\n".join(lines)


def diff_report_to_json(report: list[dict[str, Any]]) -> str:
    """Serialize diff report to JSON string.

    Args:
        report: List of diff entry dicts from generate_diff_report.

    Returns:
        JSON string with indent=2 for readability.

    Example::

        >>> entry = {"metric_name": "x", "expected": 1.0, "computed": 1.0,
        ...          "delta": 0.0, "tolerance": {"absolute": 0.05}, "passed": True}
        >>> import json
        >>> parsed = json.loads(diff_report_to_json([entry]))
        >>> len(parsed)
        1
    """
    return json.dumps(report, indent=2)


def summarize_pass_rates(
    report: list[dict[str, Any]],
    registry: MetricRegistry,
) -> dict[str, Any]:
    """Calculate P0/P1 pass rates from diff report.

    Looks up each metric's priority in the registry to compute
    per-priority breakdowns.  Returns a summary dict with total/passed/
    failed counts, overall pass rate, per-priority rates, and a list
    of failure details.

    Args:
        report: List of diff entry dicts from generate_diff_report.
        registry: MetricRegistry for priority lookups.

    Returns:
        Summary dict with keys: total, passed, failed, pass_rate,
        p0_total, p0_passed, p0_pass_rate, p1_total, p1_passed,
        p1_pass_rate, failures.

    Example::

        >>> from stockvaluefinder.validation.loader import load_metric_registry
        >>> reg = load_metric_registry()
        >>> tol = Tolerance(absolute=0.05)
        >>> cmp = ComparisonResult("m_score", -0.74, -0.74, 0.0, tol, True)
        >>> r = generate_diff_report([cmp])
        >>> s = summarize_pass_rates(r, reg)
        >>> s["total"]
        1
    """
    total = len(report)
    passed = sum(1 for entry in report if entry["passed"])
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    p0_total = 0
    p0_passed = 0
    p1_total = 0
    p1_passed = 0

    failures: list[dict[str, Any]] = []

    for entry in report:
        name = entry["metric_name"]
        entry_passed = entry["passed"]

        # Look up priority from registry
        try:
            metric_def = registry.get(name)
            priority = metric_def.priority
        except KeyError:
            # Unknown metric -- count as P2 (lowest priority)
            priority = "P2"

        if priority == "P0":
            p0_total += 1
            if entry_passed:
                p0_passed += 1
        elif priority == "P1":
            p1_total += 1
            if entry_passed:
                p1_passed += 1

        if not entry_passed:
            failures.append(
                {
                    "metric_name": name,
                    "delta": entry["delta"],
                }
            )

    p0_pass_rate = (p0_passed / p0_total * 100) if p0_total > 0 else 0.0
    p1_pass_rate = (p1_passed / p1_total * 100) if p1_total > 0 else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "p0_total": p0_total,
        "p0_passed": p0_passed,
        "p0_pass_rate": p0_pass_rate,
        "p1_total": p1_total,
        "p1_passed": p1_passed,
        "p1_pass_rate": p1_pass_rate,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestL3DiffReport:
    """Tests for L3 diff report generation and pass rate summary utilities."""

    def test_diff_report_structure(self) -> None:
        """Diff report produces correct structure with 6 keys per entry."""
        comparisons = [
            ComparisonResult(
                metric_name="m_score",
                expected=-0.7421,
                computed=-0.74,
                delta=0.0021,
                tolerance_applied=Tolerance(absolute=0.05),
                passed=True,
            ),
            ComparisonResult(
                metric_name="f_score",
                expected=6.0,
                computed=7.0,
                delta=1.0,
                tolerance_applied=Tolerance(absolute=0),
                passed=False,
            ),
            ComparisonResult(
                metric_name="roic",
                expected=0.353242,
                computed=0.353242,
                delta=0.0,
                tolerance_applied=Tolerance(relative=0.01),
                passed=True,
            ),
        ]
        report = generate_diff_report(comparisons)

        assert len(report) == 3
        for entry in report:
            assert "metric_name" in entry
            assert "expected" in entry
            assert "computed" in entry
            assert "delta" in entry
            assert "tolerance" in entry
            assert "passed" in entry

        # Tolerance dict should only have non-None keys
        assert "absolute" in report[0]["tolerance"]
        assert "relative" not in report[0]["tolerance"]
        assert report[1]["passed"] is False
        assert report[2]["tolerance"] == {"relative": 0.01}

    def test_diff_report_json_serializable(self) -> None:
        """Diff report can be serialized to JSON and back."""
        comparisons = [
            ComparisonResult("test1", 1.0, 1.01, 0.01, Tolerance(absolute=0.05), True),
            ComparisonResult("test2", 2.0, 2.5, 0.5, Tolerance(relative=0.1), False),
        ]
        report = generate_diff_report(comparisons)
        json_str = diff_report_to_json(report)
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert parsed[0]["metric_name"] == "test1"
        assert parsed[1]["passed"] is False

    def test_format_diff_table(self) -> None:
        """Formatted table contains PASS/FAIL status and metric names."""
        comparisons = [
            ComparisonResult(
                "m_score", -0.74, -0.74, 0.0, Tolerance(absolute=0.05), True
            ),
            ComparisonResult("f_score", 6.0, 7.0, 1.0, Tolerance(absolute=0), False),
        ]
        report = generate_diff_report(comparisons)
        table = format_diff_table(report)

        assert "PASS" in table
        assert "FAIL" in table
        assert "m_score" in table
        assert "f_score" in table

    def test_summarize_pass_rates(
        self, metric_registry_fixture: MetricRegistry
    ) -> None:
        """Summary correctly counts P0/P1 pass rates."""
        comparisons = [
            ComparisonResult(
                "m_score", -0.74, -0.74, 0.0, Tolerance(absolute=0.05), True
            ),
            ComparisonResult("roic", 0.35, 0.36, 0.01, Tolerance(relative=0.01), False),
        ]
        report = generate_diff_report(comparisons)
        summary = summarize_pass_rates(report, metric_registry_fixture)

        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert len(summary["failures"]) == 1

    def test_diff_report_golden_stock(
        self,
        golden_loader: Any,
        compute_metrics_from_frozen: Any,
        metric_registry_fixture: MetricRegistry,
    ) -> None:
        """Integration test: full diff report for 600519.SH/2023."""
        ticker, year, is_financial = "600519.SH", 2023, False
        expected_data = golden_loader(ticker, year)
        computed = compute_metrics_from_frozen(ticker, year, is_financial)

        comparisons: list[ComparisonResult] = []
        for name, entry in expected_data["metrics"].items():
            expected = entry.get("value")
            if expected is None:
                continue
            computed_val = computed.get(name)
            if computed_val is None:
                continue
            if isinstance(expected, bool):
                expected = 1.0 if expected else 0.0
            if isinstance(computed_val, bool):
                computed_val = 1.0 if computed_val else 0.0
            result = metric_registry_fixture.check(
                name, float(expected), float(computed_val)
            )
            comparisons.append(result)

        report = generate_diff_report(comparisons)
        assert len(report) > 0, "Diff report should have entries for non-null metrics"

        # Verify JSON serialization works
        json_str = diff_report_to_json(report)
        parsed = json.loads(json_str)
        assert len(parsed) == len(report)

        # Verify table formatting works
        table = format_diff_table(report)
        assert "PASS" in table or "FAIL" in table

        # Print for visual inspection (use pytest -s to see)
        print("\n" + table)
