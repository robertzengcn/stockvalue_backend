"""Unit tests for reconcile_core: frozen reconciliation pipeline.

Tests verify the core reconcile logic loads golden expected values,
computes metrics from frozen AKShare data, and compares using the
MetricRegistry tolerance system.  All tests depend on committed golden
dataset files (600519.SH/2023).
"""

from __future__ import annotations

import pytest

from stockvaluefinder.tools.reconcile_core import (
    load_manifest,
    lookup_is_financial,
    reconcile,
)


@pytest.mark.golden
class TestReconcileCore:
    """Tests for the frozen-mode reconcile pipeline."""

    def test_reconcile_full_600519(self) -> None:
        """Reconcile 600519.SH/2023 produces >= 10 non-null comparisons."""
        result = reconcile("600519.SH", 2023)

        assert result.ticker == "600519.SH"
        assert result.year == 2023
        assert len(result.comparisons) >= 10
        assert any(c.passed for c in result.comparisons)

    def test_reconcile_single_metric(self) -> None:
        """Reconcile with metric='m_score' returns exactly 1 entry."""
        result = reconcile("600519.SH", 2023, metric="m_score")

        assert len(result.comparisons) == 1
        assert result.comparisons[0].metric_name == "m_score"
        assert result.comparisons[0].passed is True

    def test_reconcile_nonexistent_metric(self) -> None:
        """Reconcile with a metric not in expected data returns empty comparisons."""
        result = reconcile("600519.SH", 2023, metric="does_not_exist")

        assert len(result.comparisons) == 0

    def test_reconcile_p0_status(self) -> None:
        """All P0 metrics pass for 600519.SH/2023."""
        result = reconcile("600519.SH", 2023)

        assert result.p0_all_pass is True
        assert result.summary["p0_total"] > 0
        assert result.summary["p0_pass_rate"] == 100.0

    def test_reconcile_summary_counts(self) -> None:
        """Summary total matches comparison count; passed + failed == total."""
        result = reconcile("600519.SH", 2023)

        assert result.summary["total"] == len(result.comparisons)
        assert (
            result.summary["passed"] + result.summary["failed"]
            == result.summary["total"]
        )

    def test_reconcile_missing_ticker_raises(self) -> None:
        """Reconcile with a ticker missing golden data raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            reconcile("999999.SH", 2023)

    def test_load_manifest(self) -> None:
        """Manifest loads with 14 golden stocks."""
        manifest = load_manifest()

        assert "golden_stocks" in manifest
        assert len(manifest["golden_stocks"]) == 14

    def test_lookup_is_financial(self) -> None:
        """is_financial lookup returns correct values from manifest."""
        assert lookup_is_financial("600519.SH") is False
        assert lookup_is_financial("601398.SH") is True
        assert lookup_is_financial("UNKNOWN.SH") is False
