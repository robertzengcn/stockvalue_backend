"""L3 end-to-end golden pipeline tests using frozen AKShare data.

Full pipeline: frozen JSON -> build report -> call services -> compare against
expected values.  No network required.  Parametrized over all l3_verified stocks
in manifest.yaml.

P0 metrics (M-Score, F-Score, ROIC components) use hard assertions -- 100% pass
required.  P1 metrics (detect_* , goodwill_ratio, profit_cash_divergence) use
``pytest.xfail`` on failure -- non-blocking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Metric priority lists
# ---------------------------------------------------------------------------

P0_METRICS = [
    "dsri",
    "gmi",
    "aqi",
    "sgi",
    "depi",
    "sgai",
    "lvgi",
    "tata",
    "m_score",
    "f_score",
    "nopat",
    "invested_capital",
    "roic",
]

P1_METRICS = [
    "detect_\u5b58\u8d37\u53cc\u9ad8",
    "goodwill_ratio",
    "profit_cash_divergence",
]

# Metrics that require external data (always null in expected_metrics.yaml)
SKIP_METRICS = [
    "roic_wacc_spread",
    "wacc",
    "present_value",
    "terminal_value",
    "margin_of_safety",
    "net_dividend_yield",
    "yield_gap",
    "buyback_yield",
    "capital_allocation_score",
    "resonance_score",
    "dcf_adjustment",
    "alpha_score",
]


# ---------------------------------------------------------------------------
# Parametrize helper
# ---------------------------------------------------------------------------


def _load_verified_ids() -> list[tuple[str, int, bool]]:
    """Load verified (ticker, year, is_financial) triples from manifest.

    Returns only entries where ``l3_verified`` is ``True``.
    """
    manifest_path = Path(__file__).parent / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    ids: list[tuple[str, int, bool]] = []
    for entry in manifest["golden_stocks"]:
        if entry.get("l3_verified", False):
            for year in entry["years"]:
                ids.append((entry["ticker"], year, entry.get("is_financial", False)))
    return ids


_VERIFIED_IDS = _load_verified_ids()
_VERIFIED_IDS_STR = [f"{t}_{y}" for t, y, _ in _VERIFIED_IDS]


# ---------------------------------------------------------------------------
# Inline diff-table helper (Plan 21-03 adds a dedicated module)
# ---------------------------------------------------------------------------


def _format_diff_table(
    entries: list[dict[str, Any]],
) -> str:
    """Format a simple ASCII diff table for P0 failure diagnostics."""
    if not entries:
        return ""
    header = f"{'Metric':<22} {'Expected':>14} {'Computed':>14} {'Delta':>10}"
    sep = "-" * len(header)
    rows = [header, sep]
    for e in entries:
        rows.append(
            f"{e['metric_name']:<22} {e['expected']:>14.4f} "
            f"{e['computed']:>14.4f} {e['delta']:>10.4f}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestL3GoldenFrozen:
    """L3 frozen golden pipeline tests (no network required)."""

    @pytest.mark.parametrize(
        "ticker,year,is_financial",
        _VERIFIED_IDS,
        ids=_VERIFIED_IDS_STR,
    )
    def test_l3_p0_metrics(
        self,
        ticker: str,
        year: int,
        is_financial: bool,
        golden_loader: Any,
        compute_metrics_from_frozen: Any,
        metric_registry_fixture: Any,
        assert_metric_within_tolerance: Any,
    ) -> None:
        """Assert all P0 metrics match expected values within tolerance.

        P0 failures are hard assertions -- every metric must pass.
        Metrics with null expected values or uncomputable values are skipped.
        """
        expected_data = golden_loader(ticker, year)
        computed = compute_metrics_from_frozen(ticker, year, is_financial)
        metrics_spec = expected_data["metrics"]

        failures: list[str] = []
        diff_entries: list[dict[str, Any]] = []

        for name in P0_METRICS:
            if name not in metrics_spec:
                continue
            entry = metrics_spec[name]
            expected = entry.get("value")
            if expected is None:
                skip_reason = entry.get("skip_reason", "no expected value")
                pytest.skip(f"Metric {name}: {skip_reason}")
                return  # skip the rest for this stock
            computed_val = computed.get(name)
            if computed_val is None:
                pytest.skip(f"Could not compute {name}: previous year data unavailable")
                return
            # Convert bool to float for comparison
            if isinstance(expected, bool):
                expected = 1.0 if expected else 0.0
            if isinstance(computed_val, bool):
                computed_val = 1.0 if computed_val else 0.0
            try:
                assert_metric_within_tolerance(
                    name,
                    float(expected),
                    float(computed_val),
                    metric_registry_fixture,
                )
            except AssertionError as exc:
                failures.append(str(exc))
                diff_entries.append(
                    {
                        "metric_name": name,
                        "expected": float(expected),
                        "computed": float(computed_val),
                        "delta": abs(float(computed_val) - float(expected)),
                    }
                )

        assert not failures, (
            f"P0 metric failures for {ticker}/{year}:\n"
            + "\n".join(failures)
            + (f"\n\nDiff report:\n{_format_diff_table(diff_entries)}")
        )

    @pytest.mark.parametrize(
        "ticker,year,is_financial",
        _VERIFIED_IDS,
        ids=_VERIFIED_IDS_STR,
    )
    def test_l3_p1_metrics(
        self,
        ticker: str,
        year: int,
        is_financial: bool,
        golden_loader: Any,
        compute_metrics_from_frozen: Any,
        metric_registry_fixture: Any,
        assert_metric_within_tolerance: Any,
    ) -> None:
        """Assert P1 metrics match expected values within tolerance.

        P1 failures use ``pytest.xfail`` (non-blocking).  Metrics with null
        expected values or uncomputable values are silently skipped.
        """
        expected_data = golden_loader(ticker, year)
        computed = compute_metrics_from_frozen(ticker, year, is_financial)
        metrics_spec = expected_data["metrics"]

        for name in P1_METRICS:
            if name not in metrics_spec:
                continue
            entry = metrics_spec[name]
            expected = entry.get("value")
            if expected is None:
                continue  # P1: silently skip null expected values
            computed_val = computed.get(name)
            if computed_val is None:
                continue  # P1: silently skip if uncomputable
            # Convert bool to float for comparison
            if isinstance(expected, bool):
                expected = 1.0 if expected else 0.0
            if isinstance(computed_val, bool):
                computed_val = 1.0 if computed_val else 0.0
            try:
                assert_metric_within_tolerance(
                    name,
                    float(expected),
                    float(computed_val),
                    metric_registry_fixture,
                )
            except AssertionError:
                pytest.xfail(
                    f"P1 metric '{name}' outside tolerance for {ticker}/{year}"
                )

    def test_l3_all_metrics_counted(
        self,
        golden_loader: Any,
        verified_golden_stock_ids: list[tuple[str, int]],
    ) -> None:
        """Verify every metric in expected_metrics.yaml is categorized.

        Catches cases where new metrics are added to expected_metrics.yaml
        but not classified as P0, P1, or SKIP.
        """
        all_known = set(P0_METRICS) | set(P1_METRICS) | set(SKIP_METRICS)
        for ticker, year in verified_golden_stock_ids:
            expected_data = golden_loader(ticker, year)
            for metric_name in expected_data.get("metrics", {}):
                assert metric_name in all_known, (
                    f"Metric '{metric_name}' in {ticker}/{year} "
                    f"expected_metrics.yaml is not categorized as P0, P1, "
                    f"or SKIP"
                )
