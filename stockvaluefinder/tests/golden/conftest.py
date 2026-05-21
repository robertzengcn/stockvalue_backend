"""Pytest fixtures for golden dataset loading.

Provides:
- golden_manifest: Parsed manifest.yaml
- golden_stock_ids: List of (ticker, year) tuples for ALL stocks in manifest
- verified_golden_stock_ids: List of (ticker, year) tuples filtered by l3_verified=True
- golden_loader: Callable that loads expected_metrics.yaml for a given ticker/year
- golden_manifest_entries: Dict keyed by ticker for sector/is_financial lookup

L3 End-to-End Golden Pipeline fixtures:
- metric_registry_fixture: Loaded MetricRegistry singleton
- frozen_data_loader: Callable loading frozen AKShare JSON for any stock/year
- compute_metrics_from_frozen: Full L3 pipeline from frozen data to computed metrics
- assert_metric_within_tolerance: Tolerance-based assertion using registry.check()
- load_expected_metrics: Callable loading expected_metrics.yaml for any stock/year
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
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
from stockvaluefinder.validation.loader import load_metric_registry


GOLDEN_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def golden_manifest() -> dict[str, Any]:
    """Load and return the golden manifest (manifest.yaml).

    Returns:
        Parsed manifest dictionary with ``golden_stocks`` list.
    """
    manifest_path = GOLDEN_DIR / "manifest.yaml"
    content = manifest_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


@pytest.fixture(scope="session")
def golden_stock_ids(golden_manifest: dict[str, Any]) -> list[tuple[str, int]]:
    """Return list of (ticker, year) tuples for ALL stocks in manifest.

    Returns ALL entries regardless of l3_verified status.  This is used
    for test discovery -- the l3_verified flag is used to skip tests,
    not to hide stocks from the fixture.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        List of ``(ticker, year)`` tuples for every manifest entry.
    """
    ids: list[tuple[str, int]] = []
    for entry in golden_manifest["golden_stocks"]:
        for year in entry["years"]:
            ids.append((entry["ticker"], year))
    return ids


@pytest.fixture(scope="session")
def verified_golden_stock_ids(
    golden_manifest: dict[str, Any],
) -> list[tuple[str, int]]:
    """Return list of (ticker, year) tuples ONLY for l3_verified stocks.

    Used by L3 golden tests to parametrize only against fully verified
    entries.  Stocks not yet hand-verified are excluded.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        List of ``(ticker, year)`` tuples where ``l3_verified`` is ``True``.
    """
    ids: list[tuple[str, int]] = []
    for entry in golden_manifest["golden_stocks"]:
        if entry.get("l3_verified", False):
            for year in entry["years"]:
                ids.append((entry["ticker"], year))
    return ids


@pytest.fixture(scope="session")
def golden_loader() -> Any:
    """Return a callable that loads expected_metrics.yaml for a ticker/year.

    Usage::

        def test_moutai(golden_loader):
            metrics = golden_loader("600519.SH", 2023)
            assert metrics["ticker"] == "600519.SH"

    Returns:
        Callable that accepts ``(ticker: str, year: int)`` and returns
        parsed YAML dict.
    """

    def _load(ticker: str, year: int) -> dict[str, Any]:
        path = GOLDEN_DIR / ticker / str(year) / "expected_metrics.yaml"
        if not path.exists():
            msg = f"Golden data not found: {path}"
            raise FileNotFoundError(msg)
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content)

    return _load


@pytest.fixture(scope="session")
def golden_manifest_entries(
    golden_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return dict keyed by ticker of manifest entries.

    Useful for looking up sector and is_financial by ticker.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        Dict mapping ticker string to its manifest entry dict.
    """
    return {entry["ticker"]: entry for entry in golden_manifest["golden_stocks"]}


# ---------------------------------------------------------------------------
# L3 End-to-End Golden Pipeline fixtures
# ---------------------------------------------------------------------------

# Metrics that require external market data and cannot be computed from
# frozen AKShare financial statements alone.
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

# Map calculate_mscore_indices short keys to the long keys expected by
# calculate_beneish_m_score.
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

    Frozen AKShare JSON files contain records for many periods (quarterly
    and annual).  This helper selects the record whose ``REPORT_DATE``
    matches ``{year}-12-31``.

    Args:
        records: List of AKShare record dicts.
        year: Fiscal year to find (e.g. ``2023``).

    Returns:
        Matching record with NaN/Inf sanitized, or ``None`` if not found.
    """
    period_str = f"{year}-12-31"
    period_nodash = f"{year}1231"
    for r in records:
        rd = str(r.get("REPORT_DATE", ""))
        if period_str in rd or period_nodash in rd:
            return _sanitize_nan(r)
    return None


@pytest.fixture(scope="session")
def metric_registry_fixture():
    """Load and return the MetricRegistry singleton.

    Returns:
        Validated ``MetricRegistry`` instance loaded from
        ``metric_registry.yaml``.
    """
    return load_metric_registry()


@pytest.fixture(scope="session")
def frozen_data_loader() -> Any:
    """Return a callable that loads frozen AKShare JSON for a ticker/year.

    The callable signature is ``(ticker, year) -> dict[str, dict[str, Any]]``
    where the returned dict has keys ``income``, ``balance``, ``cashflow``,
    each mapping to the annual record matching ``{year}-12-31`` from the
    corresponding frozen JSON file with NaN/Inf values sanitized to ``None``.

    The frozen JSON files contain records for many periods (quarterly and
    annual).  The loader selects the annual record for the requested year
    by matching ``REPORT_DATE`` against ``{year}-12-31``.

    Results are cached in a closure dict keyed by ``(ticker, year)``.

    Usage::

        data = frozen_data_loader("600519.SH", 2023)
        income = data["income"]
        balance = data["balance"]

    Returns:
        Callable accepting ``(ticker: str, year: int)`` and returning dict
        with ``income``, ``balance``, ``cashflow`` sub-dicts.
    """
    cache: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}

    def _load(ticker: str, year: int) -> dict[str, dict[str, Any]]:
        key = (ticker, year)
        if key in cache:
            return cache[key]

        result: dict[str, dict[str, Any]] = {}
        for statement in ("income", "balance", "cashflow"):
            path = GOLDEN_DIR / ticker / str(year) / f"raw_akshare_{statement}.json"
            if not path.exists():
                msg = f"Frozen data not found: {path}"
                raise FileNotFoundError(msg)
            with open(path, encoding="utf-8") as fh:
                raw_text = fh.read()
            data = json.loads(raw_text)
            records = data.get("records", [])
            if not records:
                msg = f"No records in frozen data: {path}"
                raise ValueError(msg)
            record = _find_record_for_period(records, year)
            if record is None:
                msg = (
                    f"No annual record for {year}-12-31 in {path}. "
                    f"Available periods: "
                    f"{[str(r.get('REPORT_DATE', 'N/A')) for r in records[:5]]}"
                )
                raise ValueError(msg)
            result[statement] = record

        cache[key] = result
        return result

    return _load


@pytest.fixture(scope="session")
def load_expected_metrics() -> Any:
    """Return a callable that loads expected_metrics.yaml for a ticker/year.

    Usage::

        metrics = load_expected_metrics("600519.SH", 2023)
        for name, spec in metrics["metrics"].items():
            if spec["value"] is not None:
                ...

    Returns:
        Callable accepting ``(ticker: str, year: int)`` and returning parsed
        YAML dict with ``metrics`` key containing metric specifications.
    """
    cache: dict[tuple[str, int], dict[str, Any]] = {}

    def _load(ticker: str, year: int) -> dict[str, Any]:
        key = (ticker, year)
        if key in cache:
            return cache[key]
        path = GOLDEN_DIR / ticker / str(year) / "expected_metrics.yaml"
        if not path.exists():
            msg = f"Expected metrics not found: {path}"
            raise FileNotFoundError(msg)
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        cache[key] = data
        return data

    return _load


@pytest.fixture(scope="session")
def compute_metrics_from_frozen(frozen_data_loader: Any) -> Any:
    """Return a callable that runs the full L3 pipeline on frozen data.

    The callable signature is
    ``(ticker, year, is_financial) -> dict[str, float | None]``.

    Steps performed:
    1. Load current-year frozen AKShare data (income/balance/cashflow).
    2. Build a standardized report using the same extraction logic as
       the production data_service.
    3. Attempt to load previous-year data.  If unavailable, all YoY
       metrics are set to ``None``.
    4. Call ``calculate_mscore_indices``, ``calculate_beneish_m_score``,
       ``calculate_piotroski_f_score``, ``detect_存贷双高``,
       ``calculate_goodwill_ratio``, ``detect_profit_cash_divergence``.
    5. Compute ROIC via ``calculate_nopat``, ``calculate_invested_capital``,
       ``calculate_roic``.
    6. Set metrics requiring external market data to ``None``.

    Returns:
        Callable returning a flat dict of ``metric_name -> float | None``.
    """
    # Lazy import to avoid circular dependency at module level.
    # These helpers replicate production data_service extraction from frozen JSON.
    from tests.unit.test_l2.conftest import (
        build_standardized_report_from_frozen,
        roic_inputs_from_frozen,
    )

    def _compute(
        ticker: str,
        year: int,
        is_financial: bool,
    ) -> dict[str, float | None]:
        # --- Current year data ---
        current_data = frozen_data_loader(ticker, year)
        current_report = build_standardized_report_from_frozen(
            current_data["income"],
            current_data["balance"],
            current_data["cashflow"],
            ticker,
            year,
        )

        # --- Try to find previous year record in the same frozen files ---
        # Frozen AKShare JSON files contain records for many years, so we
        # can extract the previous year from the same file.
        prev_year = year - 1
        previous_data: dict[str, dict[str, Any]] | None = None
        try:
            previous_data = frozen_data_loader(ticker, prev_year)
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

            # Goodwill ratio (handle None and "None" string from sanitized data)
            _gw_raw = current_report.get("goodwill")
            _eq_raw = current_report.get("equity_total") or current_report.get(
                "total_parent_equity"
            )
            goodwill_val = (
                Decimal(str(_gw_raw))
                if _gw_raw is not None and str(_gw_raw) != "None"
                else Decimal("0")
            )
            equity_val = (
                Decimal(str(_eq_raw))
                if _eq_raw is not None and str(_eq_raw) != "None"
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

            # Goodwill ratio is current-year only (no YoY dependency)
            # Handle None and "None" string from sanitized data
            _gw_raw = current_report.get("goodwill")
            _eq_raw = current_report.get("equity_total") or current_report.get(
                "total_parent_equity"
            )
            goodwill_val = (
                Decimal(str(_gw_raw))
                if _gw_raw is not None and str(_gw_raw) != "None"
                else Decimal("0")
            )
            equity_val = (
                Decimal(str(_eq_raw))
                if _eq_raw is not None and str(_eq_raw) != "None"
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
        invested_capital, negative_ic = calculate_invested_capital(
            roic_inputs["balance"]
        )
        roic = calculate_roic(nopat, invested_capital, negative_ic)
        metrics["nopat"] = nopat
        metrics["invested_capital"] = invested_capital
        metrics["roic"] = roic

        # --- Metrics requiring external market data ---
        for name in _METRICS_REQUIRING_EXTERNAL_DATA:
            metrics[name] = None

        return metrics

    return _compute


@pytest.fixture(scope="session")
def assert_metric_within_tolerance() -> Any:
    """Return a callable that asserts a metric is within tolerance.

    The callable signature is
    ``(metric_name, expected, computed, registry) -> ComparisonResult``.

    For boolean metrics (``detect_存贷双高``, ``profit_cash_divergence``),
    convert to ``float`` (``True`` -> ``1.0``, ``False`` -> ``0.0``) before
    comparison.  For integer metrics (``f_score``), pass as ``float``.

    Usage::

        result = assert_metric_within_tolerance(
            "m_score", -0.7421, -0.7400, registry,
        )

    Returns:
        Callable that raises ``AssertionError`` on failure and returns
        ``ComparisonResult`` on success.
    """
    from stockvaluefinder.validation.comparators import ComparisonResult

    def _assert(
        metric_name: str,
        expected: float,
        computed: float,
        registry: Any,
    ) -> ComparisonResult:
        # Convert booleans to floats for comparison
        if isinstance(computed, bool):
            computed = float(computed)
        if isinstance(expected, bool):
            expected = float(expected)
        # Convert integers to floats
        computed = float(computed)
        expected = float(expected)

        result = registry.check(metric_name, expected, computed)
        assert result.passed, (
            f"Metric '{metric_name}' outside tolerance: "
            f"expected={expected}, computed={computed}, "
            f"delta={result.delta}, tolerance={result.tolerance_applied}"
        )
        return result

    return _assert
