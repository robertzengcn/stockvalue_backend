"""Core reconciliation logic for comparing computed metrics against golden values.

Provides two modes:
- **Frozen mode** (``reconcile``): Loads frozen AKShare JSON from the golden dataset,
  computes all financial metrics, and compares against expected_metrics.yaml.
  No network access required -- runs entirely from committed test data.
- **Live mode** (``reconcile_live``): Fetches real data via ExternalDataService,
  computes metrics, and compares against the same golden expected values.
  Requires network access and AKShare availability.

Usage::

    from stockvaluefinder.tools.reconcile_core import reconcile

    result = reconcile("600519.SH", 2023)
    print(result.summary)
    if result.p0_all_pass:
        print("All P0 metrics pass!")
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from stockvaluefinder.services.risk_service import (
    calculate_beneish_m_score,
    calculate_goodwill_ratio,
    calculate_mscore_indices,
    calculate_piotroski_f_score,
    detect_存贷双高,
    detect_profit_cash_divergence,
)
from stockvaluefinder.services.roic_service import (
    calculate_invested_capital,
    calculate_nopat,
    calculate_roic,
)
from stockvaluefinder.validation.comparators import ComparisonResult
from stockvaluefinder.validation.loader import load_metric_registry
from stockvaluefinder.validation.schema import MetricRegistry

# Shared utilities from L2 test infrastructure -- these are standalone
# helper functions (not fixtures), safe for production import.
from tests.unit.test_l2.conftest import (
    build_standardized_report_from_frozen,
    roic_inputs_from_frozen,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden"

INDEX_KEY_MAP: dict[str, str] = {
    "dsri": "days_sales_receivables_index",
    "gmi": "gross_margin_index",
    "aqi": "asset_quality_index",
    "sgi": "sales_growth_index",
    "depi": "depreciation_index",
    "sgai": "sga_expense_index",
    "lvgi": "leverage_index",
    "tata": "total_accruals_to_assets",
}

_METRICS_REQUIRING_EXTERNAL_DATA = frozenset(
    {
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
        "roic_wacc_spread",
    }
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconcileResult:
    """Immutable result of reconciling computed metrics against golden values.

    Attributes:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year (e.g. ``2023``).
        comparisons: List of per-metric comparison results.
        summary: Pass rate summary with total/passed/failed and P0/P1 breakdowns.
        p0_all_pass: True if all P0-priority metrics pass.
        skipped_metrics: Metrics skipped due to null expected or computed values.
    """

    ticker: str
    year: int
    comparisons: list[ComparisonResult]
    summary: dict[str, Any]
    p0_all_pass: bool
    skipped_metrics: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_nan(obj: Any) -> Any:
    """Walk a data structure and replace NaN/Inf floats with None."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(item) for item in obj]
    return obj


def _find_record_for_period(
    records: list[dict[str, Any]],
    year: int,
) -> dict[str, Any] | None:
    """Find the annual record matching ``{year}-12-31`` in a list of records.

    Args:
        records: List of AKShare record dicts.
        year: Fiscal year to find.

    Returns:
        Matching record with NaN/Inf sanitized, or ``None``.
    """
    period_str = f"{year}-12-31"
    period_nodash = f"{year}1231"
    for r in records:
        rd = str(r.get("REPORT_DATE", ""))
        if period_str in rd or period_nodash in rd:
            return _sanitize_nan(r)
    return None


def _load_frozen_records(
    ticker: str, year: int, statement: str
) -> list[dict[str, Any]]:
    """Load all records from a frozen AKShare JSON file.

    Args:
        ticker: Stock ticker.
        year: Fiscal year.
        statement: One of ``income``, ``balance``, ``cashflow``.

    Returns:
        List of record dicts from the frozen file.

    Raises:
        FileNotFoundError: If the frozen JSON file does not exist.
    """
    path = GOLDEN_DIR / ticker / str(year) / f"raw_akshare_{statement}.json"
    if not path.exists():
        msg = f"Frozen data not found for {ticker}/{year}: {statement}"
        raise FileNotFoundError(msg)
    with open(path, encoding="utf-8") as fh:
        data = json.loads(fh.read())
    return data.get("records", [])


def _compute_pass_rate_summary(
    comparisons: list[ComparisonResult],
    registry: MetricRegistry,
) -> dict[str, Any]:
    """Calculate P0/P1 pass rates from comparison results.

    Replicates the logic from ``summarize_pass_rates`` in
    ``test_l3_diff_report.py``, but operates directly on
    ``ComparisonResult`` objects instead of dicts.

    Args:
        comparisons: List of ComparisonResult objects.
        registry: MetricRegistry for priority lookups.

    Returns:
        Summary dict with total/passed/failed, pass_rate,
        p0_total/p0_passed/p0_pass_rate, p1_total/p1_passed/p1_pass_rate,
        and failures list.
    """
    total = len(comparisons)
    passed = sum(1 for c in comparisons if c.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    p0_total = 0
    p0_passed = 0
    p1_total = 0
    p1_passed = 0

    failures: list[dict[str, Any]] = []

    for cmp in comparisons:
        name = cmp.metric_name
        entry_passed = cmp.passed

        try:
            metric_def = registry.get(name)
            priority = metric_def.priority
        except KeyError:
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
            failures.append({"metric_name": name, "delta": cmp.delta})

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
# Public API: data loading
# ---------------------------------------------------------------------------


def load_manifest() -> dict[str, Any]:
    """Load the golden stock manifest (``manifest.yaml``).

    Returns:
        Parsed manifest dict with ``golden_stocks`` list.
    """
    manifest_path = GOLDEN_DIR / "manifest.yaml"
    content = manifest_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


def lookup_is_financial(ticker: str) -> bool:
    """Check if a ticker is in the financial sector per the manifest.

    Args:
        ticker: Stock ticker (e.g. ``"601398.SH"``).

    Returns:
        ``True`` if ``is_financial`` is set in the manifest entry,
        ``False`` otherwise (including when ticker is not found).
    """
    manifest = load_manifest()
    for entry in manifest["golden_stocks"]:
        if entry["ticker"] == ticker:
            return bool(entry.get("is_financial", False))
    return False


def load_expected_metrics_for_ticker(ticker: str, year: int) -> dict[str, Any]:
    """Load golden expected metrics YAML for a specific ticker and year.

    Args:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year (e.g. ``2023``).

    Returns:
        Parsed YAML dict with ``metrics`` key containing metric specifications.

    Raises:
        FileNotFoundError: If expected_metrics.yaml does not exist for the
            given ticker/year.
    """
    path = GOLDEN_DIR / ticker / str(year) / "expected_metrics.yaml"
    if not path.exists():
        msg = f"Golden expected metrics not found for {ticker}/{year}. Expected: {path}"
        raise FileNotFoundError(msg)
    content = path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


# ---------------------------------------------------------------------------
# Public API: frozen-mode computation
# ---------------------------------------------------------------------------


def compute_metrics_for_ticker(
    ticker: str, year: int, is_financial: bool
) -> dict[str, float | None]:
    """Compute all financial metrics from frozen AKShare golden data.

    Replicates the L3 pipeline from ``compute_metrics_from_frozen`` in
    ``tests/golden/conftest.py``, but as a standalone production function
    with no test dependency.

    Steps:
        1. Load current-year frozen AKShare data (income/balance/cashflow).
        2. Build standardized report using the same extraction logic as
           the production data_service.
        3. Attempt to load previous-year data; if unavailable, all YoY
           metrics are set to ``None``.
        4. Compute M-Score (8 indices + composite), F-Score, detect 存贷双高,
           goodwill ratio, profit-cash divergence.
        5. Compute ROIC via NOPAT / invested capital.
        6. Set metrics requiring external market data to ``None``.

    Args:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year (e.g. ``2023``).
        is_financial: Whether the stock is in the financial sector.

    Returns:
        Flat dict mapping metric name to computed value (``float`` or ``None``).
    """
    # --- Current year data ---
    current_data: dict[str, dict[str, Any]] = {}
    for statement in ("income", "balance", "cashflow"):
        records = _load_frozen_records(ticker, year, statement)
        record = _find_record_for_period(records, year)
        if record is None:
            msg = (
                f"No annual record for {year}-12-31 in frozen {statement} "
                f"data for {ticker}"
            )
            raise ValueError(msg)
        current_data[statement] = record

    current_report = build_standardized_report_from_frozen(
        current_data["income"],
        current_data["balance"],
        current_data["cashflow"],
        ticker,
        year,
    )

    # --- Try previous year ---
    prev_year = year - 1
    previous_data: dict[str, dict[str, Any]] | None = None
    try:
        prev_records: dict[str, dict[str, Any]] = {}
        for statement in ("income", "balance", "cashflow"):
            raw_records = _load_frozen_records(ticker, year, statement)
            rec = _find_record_for_period(raw_records, prev_year)
            if rec is None:
                raise ValueError(  # noqa: TRY301
                    f"No {prev_year} record in frozen {statement} for {ticker}"
                )
            prev_records[statement] = rec
        previous_data = prev_records
    except (FileNotFoundError, ValueError):
        previous_data = None

    has_previous = previous_data is not None
    metrics: dict[str, float | None] = {}

    if has_previous and previous_data is not None:
        previous_report = build_standardized_report_from_frozen(
            previous_data["income"],
            previous_data["balance"],
            previous_data["cashflow"],
            ticker,
            prev_year,
        )

        # M-Score 8 sub-indices
        indices_result = calculate_mscore_indices(
            current_report,
            previous_report,
            source_name="AKShare(frozen)",
        )
        for idx_name in (
            "dsri",
            "gmi",
            "aqi",
            "sgi",
            "depi",
            "sgai",
            "lvgi",
            "tata",
        ):
            val = indices_result.get(idx_name)
            metrics[idx_name] = float(val) if val is not None else None

        # M-Score composite
        m_score_input = {
            INDEX_KEY_MAP[k]: v
            for k, v in indices_result.items()
            if k in INDEX_KEY_MAP and v is not None
        }
        m_score_result = calculate_beneish_m_score(m_score_input, {})
        metrics["m_score"] = m_score_result["m_score"]

        # Piotroski F-Score
        fscore_result = calculate_piotroski_f_score(current_report, previous_report)
        metrics["f_score"] = float(fscore_result["f_score"])

        # Detect 存贷双高
        存贷双高_result = detect_存贷双高(current_report, previous_report)
        metrics["detect_存贷双高"] = float(存贷双高_result["存贷双高"])

        # Goodwill ratio (current-year only, handle None/"None" strings)
        _gw_raw = current_report.get("goodwill")
        _eq_raw = current_report.get("equity_total") or current_report.get(
            "total_parent_equity"
        )
        goodwill_val = (
            Decimal(str(_gw_raw))
            if _gw_raw is not None and str(_gw_raw) not in ("None", "")
            else Decimal("0")
        )
        equity_val = (
            Decimal(str(_eq_raw))
            if _eq_raw is not None and str(_eq_raw) not in ("None", "")
            else Decimal("0")
        )
        goodwill_result = calculate_goodwill_ratio(goodwill_val, equity_val)
        metrics["goodwill_ratio"] = float(goodwill_result["ratio"])

        # Profit-cash divergence
        current_ni = Decimal(str(current_report.get("net_income", 0)))
        previous_ni = Decimal(str(previous_report.get("net_income", 0)))
        current_ocf = Decimal(str(current_report.get("operating_cash_flow", 0)))
        previous_ocf = Decimal(str(previous_report.get("operating_cash_flow", 0)))
        divergence_result = detect_profit_cash_divergence(
            current_ni,
            previous_ni,
            current_ocf,
            previous_ocf,
        )
        metrics["profit_cash_divergence"] = float(divergence_result["divergence"])
    else:
        # No previous year -- all YoY metrics are None
        for idx_name in (
            "dsri",
            "gmi",
            "aqi",
            "sgi",
            "depi",
            "sgai",
            "lvgi",
            "tata",
        ):
            metrics[idx_name] = None
        metrics["m_score"] = None
        metrics["f_score"] = None
        metrics["detect_存贷双高"] = None
        metrics["profit_cash_divergence"] = None

        # Goodwill ratio is current-year only
        _gw_raw = current_report.get("goodwill")
        _eq_raw = current_report.get("equity_total") or current_report.get(
            "total_parent_equity"
        )
        goodwill_val = (
            Decimal(str(_gw_raw))
            if _gw_raw is not None and str(_gw_raw) not in ("None", "")
            else Decimal("0")
        )
        equity_val = (
            Decimal(str(_eq_raw))
            if _eq_raw is not None and str(_eq_raw) not in ("None", "")
            else Decimal("0")
        )
        goodwill_result = calculate_goodwill_ratio(goodwill_val, equity_val)
        metrics["goodwill_ratio"] = float(goodwill_result["ratio"])

    # --- ROIC (uses raw frozen data, not standardized report) ---
    roic_inputs = roic_inputs_from_frozen(
        current_data["income"],
        current_data["balance"],
    )
    nopat, _nopat_audit = calculate_nopat(roic_inputs["profit"], is_financial)
    invested_capital, negative_ic = calculate_invested_capital(roic_inputs["balance"])
    roic = calculate_roic(nopat, invested_capital, negative_ic)
    metrics["nopat"] = nopat
    metrics["invested_capital"] = invested_capital
    metrics["roic"] = roic

    # --- Metrics requiring external market data ---
    for name in _METRICS_REQUIRING_EXTERNAL_DATA:
        metrics[name] = None

    return metrics


# ---------------------------------------------------------------------------
# Public API: frozen-mode reconciliation
# ---------------------------------------------------------------------------


def reconcile(
    ticker: str,
    year: int,
    metric: str | None = None,
) -> ReconcileResult:
    """Reconcile computed metrics against golden expected values (frozen mode).

    Loads golden expected values, computes metrics from frozen AKShare data,
    compares each metric using the MetricRegistry tolerance system, and
    returns a structured ``ReconcileResult``.

    Args:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year (e.g. ``2023``).
        metric: Optional single metric name to filter to.  If ``None``,
            all non-null metrics are compared.

    Returns:
        ``ReconcileResult`` with comparisons, summary, and pass status.

    Raises:
        FileNotFoundError: If golden data files are missing for the ticker/year.
    """
    registry = load_metric_registry()
    expected_data = load_expected_metrics_for_ticker(ticker, year)
    is_financial = lookup_is_financial(ticker)
    computed = compute_metrics_for_ticker(ticker, year, is_financial)

    comparisons: list[ComparisonResult] = []
    skipped_metrics: list[str] = []

    for name, entry in expected_data["metrics"].items():
        expected = entry.get("value")

        # Skip metrics with null expected values
        if expected is None:
            skipped_metrics.append(name)
            continue

        # Apply metric filter
        if metric is not None and name != metric:
            continue

        computed_val = computed.get(name)

        # Skip if computed value is None (metric could not be calculated)
        if computed_val is None:
            skipped_metrics.append(name)
            continue

        # Convert booleans to float for tolerance comparison
        if isinstance(expected, bool):
            expected = 1.0 if expected else 0.0
        if isinstance(computed_val, bool):
            computed_val = 1.0 if computed_val else 0.0

        result = registry.check(name, float(expected), float(computed_val))
        comparisons.append(result)

    summary = _compute_pass_rate_summary(comparisons, registry)

    p0_all_pass = summary["p0_total"] > 0 and summary["p0_pass_rate"] == 100.0

    return ReconcileResult(
        ticker=ticker,
        year=year,
        comparisons=comparisons,
        summary=summary,
        p0_all_pass=p0_all_pass,
        skipped_metrics=skipped_metrics,
    )


# ---------------------------------------------------------------------------
# Public API: live-mode reconciliation
# ---------------------------------------------------------------------------


async def reconcile_live(
    ticker: str,
    year: int,
    metric: str | None = None,
    registry: MetricRegistry | None = None,
) -> ReconcileResult:
    """Reconcile computed metrics against golden expected values (live mode).

    Fetches live data from AKShare via ExternalDataService, computes metrics,
    and compares against the golden expected_metrics.yaml.  Requires network
    access and AKShare availability.

    Args:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year.
        metric: Optional single metric name to filter to.
        registry: Optional pre-loaded MetricRegistry.  If ``None``, loads
            a fresh instance.

    Returns:
        ``ReconcileResult`` with comparisons, summary, and pass status.

    Raises:
        FileNotFoundError: If golden expected_metrics.yaml is missing.
        ExternalAPIError: If data fetching fails.
    """
    from stockvaluefinder.external.data_service import ExternalDataService

    if registry is None:
        registry = load_metric_registry()

    expected_data = load_expected_metrics_for_ticker(ticker, year)
    is_financial = lookup_is_financial(ticker)

    # --- Fetch live data ---
    service = ExternalDataService(tushare_token="", enable_akshare=True)
    await service.initialize()

    try:
        current_report = await service.get_financial_report(ticker, year)

        # Attempt to fetch previous year report for YoY metrics
        prev_year = year - 1
        try:
            previous_report = await service.get_financial_report(ticker, prev_year)
        except Exception:
            previous_report = None

        # --- Compute metrics from live data ---
        metrics: dict[str, float | None] = {}

        if previous_report is not None:
            # M-Score 8 sub-indices
            indices_result = calculate_mscore_indices(
                current_report,
                previous_report,
                source_name="AKShare(live)",
            )
            for idx_name in (
                "dsri",
                "gmi",
                "aqi",
                "sgi",
                "depi",
                "sgai",
                "lvgi",
                "tata",
            ):
                val = indices_result.get(idx_name)
                metrics[idx_name] = float(val) if val is not None else None

            # M-Score composite
            m_score_input = {
                INDEX_KEY_MAP[k]: v
                for k, v in indices_result.items()
                if k in INDEX_KEY_MAP and v is not None
            }
            m_score_result = calculate_beneish_m_score(m_score_input, {})
            metrics["m_score"] = m_score_result["m_score"]

            # Piotroski F-Score
            fscore_result = calculate_piotroski_f_score(current_report, previous_report)
            metrics["f_score"] = float(fscore_result["f_score"])

            # Detect 存贷双高
            存贷双高_result = detect_存贷双高(current_report, previous_report)
            metrics["detect_存贷双高"] = float(存贷双高_result["存贷双高"])

            # Profit-cash divergence
            current_ni = Decimal(str(current_report.get("net_income", 0)))
            previous_ni = Decimal(str(previous_report.get("net_income", 0)))
            current_ocf = Decimal(str(current_report.get("operating_cash_flow", 0)))
            previous_ocf = Decimal(str(previous_report.get("operating_cash_flow", 0)))
            divergence_result = detect_profit_cash_divergence(
                current_ni,
                previous_ni,
                current_ocf,
                previous_ocf,
            )
            metrics["profit_cash_divergence"] = float(divergence_result["divergence"])
        else:
            for idx_name in (
                "dsri",
                "gmi",
                "aqi",
                "sgi",
                "depi",
                "sgai",
                "lvgi",
                "tata",
            ):
                metrics[idx_name] = None
            metrics["m_score"] = None
            metrics["f_score"] = None
            metrics["detect_存贷双高"] = None
            metrics["profit_cash_divergence"] = None

        # Goodwill ratio (current-year only)
        _gw_raw = current_report.get("goodwill")
        _eq_raw = current_report.get("equity_total") or current_report.get(
            "total_parent_equity"
        )
        goodwill_val = (
            Decimal(str(_gw_raw))
            if _gw_raw is not None and str(_gw_raw) not in ("None", "")
            else Decimal("0")
        )
        equity_val = (
            Decimal(str(_eq_raw))
            if _eq_raw is not None and str(_eq_raw) not in ("None", "")
            else Decimal("0")
        )
        goodwill_result = calculate_goodwill_ratio(goodwill_val, equity_val)
        metrics["goodwill_ratio"] = float(goodwill_result["ratio"])

        # ROIC (live mode uses get_roic_inputs from data_service)
        try:
            roic_data = await service.get_roic_inputs(ticker, year)
            nopat, _nopat_audit = calculate_nopat(roic_data["profit"], is_financial)
            invested_capital, negative_ic = calculate_invested_capital(
                roic_data["balance"]
            )
            roic = calculate_roic(nopat, invested_capital, negative_ic)
            metrics["nopat"] = nopat
            metrics["invested_capital"] = invested_capital
            metrics["roic"] = roic
        except Exception:
            metrics["nopat"] = None
            metrics["invested_capital"] = None
            metrics["roic"] = None

        # Metrics requiring external market data
        for name in _METRICS_REQUIRING_EXTERNAL_DATA:
            metrics[name] = None

    finally:
        await service.shutdown()

    # --- Compare against golden expected values ---
    comparisons: list[ComparisonResult] = []
    skipped_metrics: list[str] = []

    for name, entry in expected_data["metrics"].items():
        expected = entry.get("value")

        if expected is None:
            skipped_metrics.append(name)
            continue

        if metric is not None and name != metric:
            continue

        computed_val = metrics.get(name)

        if computed_val is None:
            skipped_metrics.append(name)
            continue

        if isinstance(expected, bool):
            expected = 1.0 if expected else 0.0
        if isinstance(computed_val, bool):
            computed_val = 1.0 if computed_val else 0.0

        result = registry.check(name, float(expected), float(computed_val))
        comparisons.append(result)

    summary = _compute_pass_rate_summary(comparisons, registry)
    p0_all_pass = summary["p0_total"] > 0 and summary["p0_pass_rate"] == 100.0

    return ReconcileResult(
        ticker=ticker,
        year=year,
        comparisons=comparisons,
        summary=summary,
        p0_all_pass=p0_all_pass,
        skipped_metrics=skipped_metrics,
    )
