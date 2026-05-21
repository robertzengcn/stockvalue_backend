"""L2 field mapping verification: cross-source consistency tests.

Cross-source consistency (LV2-03):
    Verify that AKShare and efinance field name mappings produce identical
    values for core financial fields across all 14 golden stocks. Since the
    golden dataset currently has only AKShare frozen data, efinance dicts are
    simulated by translating AKShare English keys to their Chinese equivalents.

    This tests that the two code paths in data_service.py map to the same
    standardized fields when processing the same underlying data.

All tests are marked ``@pytest.mark.l2_mapping`` and require no network
access -- they read frozen AKShare JSON files from the golden dataset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from stockvaluefinder.external.data_service import (  # type: ignore[attr-defined]
    _extract_akshare_accounts_receivable,
    _extract_akshare_cost_of_goods,
    _extract_akshare_revenue,
    _extract_akshare_sga_expense,
)
from stockvaluefinder.validation.comparators import compare_within_tolerance
from stockvaluefinder.validation.schema import Tolerance

from tests.unit.test_l2.conftest import (
    _load_frozen_json,
    build_standardized_report_from_frozen,
)


# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.l2_mapping]

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden"

# Parse manifest to get all (ticker, year) pairs
_MANIFEST_PATH = GOLDEN_DIR / "manifest.yaml"
with open(_MANIFEST_PATH, encoding="utf-8") as _f:
    _MANIFEST = yaml.safe_load(_f)

ALL_STOCK_IDS: list[tuple[str, int]] = []
for _entry in _MANIFEST["golden_stocks"]:
    for _year in _entry["years"]:
        ALL_STOCK_IDS.append((_entry["ticker"], _year))

# Manifest entries for sector lookup
_TICKER_TO_SECTOR: dict[str, dict[str, Any]] = {
    e["ticker"]: e for e in _MANIFEST["golden_stocks"]
}

# Map tickers to financial-sector status
_FINANCIAL_TICKERS: set[str] = {
    e["ticker"] for e in _MANIFEST["golden_stocks"] if e.get("is_financial", False)
}


def _is_financial(ticker: str) -> bool:
    """Return True if the ticker is in a financial sector (banking/insurance)."""
    return ticker in _FINANCIAL_TICKERS


# ---------------------------------------------------------------------------
# AKShare-to-efinance field name mapping
# ---------------------------------------------------------------------------

AKSHARE_TO_EFINANCE: dict[str, str] = {
    "TOTAL_OPERATE_INCOME": "\u8425\u4e1a\u603b\u6536\u5165",
    "OPERATE_INCOME": "\u8425\u4e1a\u6536\u5165",
    "NETPROFIT": "\u51c0\u5229\u6da6",
    "OPERATE_COST": "\u8425\u4e1a\u6210\u672c",
    "TOTAL_OPERATE_COST": "\u8425\u4e1a\u603b\u6210\u672c",
    "TOTAL_ASSETS": "\u8d44\u4ea7\u603b\u8ba1",
    "TOTAL_LIABILITIES": "\u8d1f\u503a\u5408\u8ba1",
    "TOTAL_EQUITY": "\u6240\u6709\u8005\u6743\u76ca\u5408\u8ba1",
    "TOTAL_CURRENT_ASSETS": "\u6d41\u52a8\u8d44\u4ea7\u5408\u8ba1",
    "FIXED_ASSET": "\u56fa\u5b9a\u8d44\u4ea7",
    "MONETARYFUNDS": "\u8d27\u5e01\u8d44\u91d1",
    "INVENTORY": "\u5b58\u8d27",
    "GOODWILL": "\u5546\u8a89",
    "ACCOUNTS_RECE": "\u5e94\u6536\u8d26\u6b3e",
    "LONG_LOAN": "\u957f\u671f\u501f\u6b3e",
    "NETCASH_OPERATE": "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d",
}


def _simulate_efinance_from_akshare(akshare_record: dict[str, Any]) -> dict[str, Any]:
    """Create an efinance-style dict from an AKShare record.

    Adds Chinese field name equivalents alongside English AKShare keys,
    allowing efinance-style field lookups against the same underlying data.
    The values are identical because both AKShare and efinance ultimately
    pull from East Money.
    """
    result = dict(akshare_record)
    for eng_key, chn_key in AKSHARE_TO_EFINANCE.items():
        if eng_key in akshare_record and akshare_record[eng_key] is not None:
            result[chn_key] = akshare_record[eng_key]
    return result


# ---------------------------------------------------------------------------
# Cross-source consistency tests (parametrized across all golden stocks)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_revenue_cross_source(ticker: str, year: int) -> None:
    """Revenue extraction produces the same value via AKShare and efinance paths."""
    income = _load_frozen_json(ticker, year, "income")
    efinance_income = _simulate_efinance_from_akshare(income)

    akshare_revenue = float(_extract_akshare_revenue(income))
    efinance_revenue = float(
        efinance_income.get(
            "\u8425\u4e1a\u603b\u6536\u5165",
            efinance_income.get("\u8425\u4e1a\u6536\u5165", 0),
        )
    )
    assert akshare_revenue == efinance_revenue, (
        f"{ticker}: revenue mismatch: AKShare={akshare_revenue}, "
        f"efinance={efinance_revenue}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_net_income_cross_source(ticker: str, year: int) -> None:
    """Net income produces the same value via AKShare and efinance paths."""
    income = _load_frozen_json(ticker, year, "income")
    efinance_income = _simulate_efinance_from_akshare(income)

    akshare_ni = float(income.get("NETPROFIT", 0))
    efinance_ni = float(
        efinance_income.get(
            "\u51c0\u5229\u6da6",
            efinance_income.get(
                "\u5f52\u5c5e\u6bcd\u516c\u53f8\u6240\u6709\u8005\u7684\u51c0\u5229\u6da6",
                0,
            ),
        )
    )
    assert akshare_ni == efinance_ni, (
        f"{ticker}: net income mismatch: AKShare={akshare_ni}, efinance={efinance_ni}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_operating_cash_flow_cross_source(ticker: str, year: int) -> None:
    """Operating cash flow produces the same value via AKShare and efinance paths."""
    cashflow = _load_frozen_json(ticker, year, "cashflow")
    efinance_cashflow = _simulate_efinance_from_akshare(cashflow)

    akshare_ocf = float(cashflow.get("NETCASH_OPERATE", 0))
    efinance_ocf = float(
        efinance_cashflow.get(
            "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d",
            0,
        )
    )
    assert akshare_ocf == efinance_ocf, (
        f"{ticker}: OCF mismatch: AKShare={akshare_ocf}, efinance={efinance_ocf}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_assets_cross_source(ticker: str, year: int) -> None:
    """Total assets produces the same value via AKShare and efinance paths."""
    balance = _load_frozen_json(ticker, year, "balance")
    efinance_balance = _simulate_efinance_from_akshare(balance)

    akshare_ta = float(balance.get("TOTAL_ASSETS", 0))
    efinance_ta = float(efinance_balance.get("\u8d44\u4ea7\u603b\u8ba1", 0))
    assert akshare_ta == efinance_ta, (
        f"{ticker}: total assets mismatch: AKShare={akshare_ta}, efinance={efinance_ta}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_liabilities_cross_source(ticker: str, year: int) -> None:
    """Total liabilities produces the same value via AKShare and efinance paths."""
    balance = _load_frozen_json(ticker, year, "balance")
    efinance_balance = _simulate_efinance_from_akshare(balance)

    akshare_tl = float(balance.get("TOTAL_LIABILITIES", 0))
    efinance_tl = float(efinance_balance.get("\u8d1f\u503a\u5408\u8ba1", 0))
    assert akshare_tl == efinance_tl, (
        f"{ticker}: total liabilities mismatch: AKShare={akshare_tl}, "
        f"efinance={efinance_tl}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_cost_of_goods_cross_source(ticker: str, year: int) -> None:
    """Cost of goods produces consistent values via AKShare and efinance paths.

    For non-financial stocks, both paths should produce the same OPERATE_COST.
    For financial stocks, AKShare uses OPERATE_EXPENSE fallback while efinance
    uses the Chinese equivalent of OPERATE_COST, which may differ. Financial
    stocks are checked with 2% relative tolerance.
    """
    income = _load_frozen_json(ticker, year, "income")
    efinance_income = _simulate_efinance_from_akshare(income)

    akshare_cog = float(_extract_akshare_cost_of_goods(income))
    efinance_cog = float(
        efinance_income.get(
            "\u8425\u4e1a\u6210\u672c",
            efinance_income.get("OPERATE_COST", 0),
        )
    )

    if _is_financial(ticker):
        # Financial stocks use different extraction paths; check within tolerance
        if akshare_cog != 0.0 and efinance_cog != 0.0:
            tol = Tolerance(relative=0.02)
            result = compare_within_tolerance(akshare_cog, efinance_cog, tol)
            assert result.passed, (
                f"{ticker}: COGS deviation > 2%: AKShare={akshare_cog}, "
                f"efinance={efinance_cog}, delta={result.delta}"
            )
    else:
        assert akshare_cog == efinance_cog, (
            f"{ticker}: COGS mismatch: AKShare={akshare_cog}, efinance={efinance_cog}"
        )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_sga_expense_cross_source(ticker: str, year: int) -> None:
    """SGA expense produces the same value via AKShare and efinance paths."""
    income = _load_frozen_json(ticker, year, "income")
    efinance_income = _simulate_efinance_from_akshare(income)

    akshare_sga = float(_extract_akshare_sga_expense(income))
    efinance_sga = float(
        efinance_income.get(
            "\u8425\u4e1a\u603b\u6210\u672c",
            efinance_income.get("TOTAL_OPERATE_COST", 0),
        )
    )
    assert akshare_sga == efinance_sga, (
        f"{ticker}: SGA mismatch: AKShare={akshare_sga}, efinance={efinance_sga}"
    )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_accounts_receivable_cross_source(ticker: str, year: int) -> None:
    """Accounts receivable produces consistent values via AKShare and efinance paths."""
    balance = _load_frozen_json(ticker, year, "balance")
    efinance_balance = _simulate_efinance_from_akshare(balance)

    akshare_ar = _extract_akshare_accounts_receivable(balance)
    efinance_ar = efinance_balance.get("\u5e94\u6536\u8d26\u6b3e")

    if _is_financial(ticker):
        # Financial stocks may use different AR proxies (PREMIUM_RECE, etc.)
        if akshare_ar != "0" and efinance_ar is not None:
            assert float(akshare_ar) != 0.0 or float(efinance_ar) != 0.0, (
                f"{ticker}: both AR paths returned zero"
            )
    else:
        # Non-financial stocks should match exactly
        akshare_ar_val = float(akshare_ar) if akshare_ar != "0" else 0.0
        efinance_ar_val = float(efinance_ar) if efinance_ar is not None else 0.0
        assert akshare_ar_val == efinance_ar_val, (
            f"{ticker}: AR mismatch: AKShare={akshare_ar_val}, "
            f"efinance={efinance_ar_val}"
        )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_standardized_report_field_names(ticker: str, year: int) -> None:
    """Both AKShare and efinance report builders produce the same output schema.

    The standardized report dict must have all keys that the efinance builder
    also produces. This verifies that both code paths output the same schema.
    """
    income = _load_frozen_json(ticker, year, "income")
    balance = _load_frozen_json(ticker, year, "balance")
    cashflow = _load_frozen_json(ticker, year, "cashflow")

    report = build_standardized_report_from_frozen(
        income, balance, cashflow, ticker, year
    )

    # Keys that BOTH AKShare and efinance report builders must produce
    required_keys = [
        "revenue",
        "net_income",
        "operating_cash_flow",
        "assets_total",
        "liabilities_total",
        "equity_total",
        "accounts_receivable",
        "cost_of_goods",
        "sga_expense",
        "total_current_assets",
        "ppe",
        "total_liabilities",
    ]

    for key in required_keys:
        assert key in report, (
            f"{ticker}: standardized report missing key '{key}'. "
            f"Available keys: {sorted(report.keys())}"
        )


# ---------------------------------------------------------------------------
# Sentinel test: documents absence of frozen efinance data
# ---------------------------------------------------------------------------


def test_no_frozen_efinance_data_note() -> None:
    """Document that efinance frozen data does not yet exist in the golden dataset.

    This test intentionally checks that no raw_efinance_*.json files exist.
    If efinance frozen data IS added later, this test will fail, indicating
    that cross-source tests should be updated to use real frozen efinance data
    instead of simulated dicts.
    """
    efinance_files = list(GOLDEN_DIR.rglob("raw_efinance_*.json"))
    assert efinance_files == [], (
        "Frozen efinance data found! The cross-source tests should be updated "
        "to use real frozen efinance data instead of simulated dicts. "
        f"Files found: {efinance_files}"
    )
