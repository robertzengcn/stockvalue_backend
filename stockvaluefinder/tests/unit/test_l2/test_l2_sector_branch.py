"""L2 field mapping verification: sector-branch verification tests.

Sector-branch verification (LV2-04):
    Verify that financial stocks (banks, insurers, securities) correctly trigger
    financial-sector extraction paths while non-financial stocks use the standard
    path. Tests cover:
    - is_financial_sector classification
    - ORG_TYPE field validation against manifest is_financial flag
    - Financial-sector field extraction (OPERATE_EXPENSE fallback, OPERATE_PROFIT)
    - Non-financial field extraction (OPERATE_COST, FINANCE_EXPENSE)
    - NOPAT formula branching (financial vs non-financial)

All tests are marked ``@pytest.mark.l2_mapping`` and require no network
access -- they read frozen AKShare JSON files from the golden dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from stockvaluefinder.config import roic_config
from stockvaluefinder.external.data_service import (  # type: ignore[attr-defined]
    _coalesce_akshare_field,
    _extract_akshare_cost_of_goods,
)
from stockvaluefinder.services.roic_service import (
    calculate_nopat,
    is_financial_sector,
)

from tests.unit.test_l2.conftest import _load_frozen_json


# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.l2_mapping]

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden"

# Parse manifest to derive financial/non-financial stock lists
_MANIFEST_PATH = GOLDEN_DIR / "manifest.yaml"
with open(_MANIFEST_PATH, encoding="utf-8") as _f:
    _MANIFEST = yaml.safe_load(_f)

FINANCIAL_STOCKS: list[tuple[str, int]] = []
NON_FINANCIAL_STOCKS: list[tuple[str, int]] = []

for _entry in _MANIFEST["golden_stocks"]:
    for _year in _entry["years"]:
        pair = (_entry["ticker"], _year)
        if _entry.get("is_financial", False):
            FINANCIAL_STOCKS.append(pair)
        else:
            NON_FINANCIAL_STOCKS.append(pair)


# ===================================================================
# Sector detection tests (specific inputs, not parametrized)
# ===================================================================


def test_is_financial_bank() -> None:
    """Banking sector string is classified as financial."""
    assert is_financial_sector("\u94f6\u884cII") is True


def test_is_financial_insurance() -> None:
    """Insurance sector string is classified as financial."""
    assert is_financial_sector("\u4fdd\u9669II") is True


def test_is_financial_securities() -> None:
    """Securities sector string is classified as financial."""
    assert is_financial_sector("\u8bc1\u5238II") is True


def test_not_financial_consumer() -> None:
    """Consumer staples sector string is NOT classified as financial."""
    assert is_financial_sector("\u767d\u9152II") is False


def test_not_financial_empty() -> None:
    """Empty string is NOT classified as financial."""
    assert is_financial_sector("") is False


def test_not_financial_real_estate() -> None:
    """Real estate sector string is NOT classified as financial."""
    assert is_financial_sector("\u623f\u5730\u4ea7") is False


def test_not_financial_tech() -> None:
    """Technology sector string is NOT classified as financial."""
    assert is_financial_sector("\u901a\u4fe1\u8bbe\u5907") is False


# ===================================================================
# Financial stock field extraction tests (parametrized)
# ===================================================================


@pytest.mark.parametrize("ticker,year", FINANCIAL_STOCKS)
def test_financial_org_type(ticker: str, year: int) -> None:
    """Financial stocks have ORG_TYPE containing a financial keyword."""
    income = _load_frozen_json(ticker, year, "income")
    org_type = income.get("ORG_TYPE", "")
    keywords = roic_config.FINANCIAL_SECTOR_KEYWORDS
    assert any(kw in str(org_type) for kw in keywords), (
        f"{ticker}: ORG_TYPE '{org_type}' does not contain any financial "
        f"keyword from {keywords}"
    )


@pytest.mark.parametrize("ticker,year", FINANCIAL_STOCKS)
def test_financial_operate_cost_null(ticker: str, year: int) -> None:
    """Financial stocks have null/NaN OPERATE_COST field.

    Banks and insurers do not report a standard cost of goods sold.
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _coalesce_akshare_field(income, "OPERATE_COST")
    assert result is None, (
        f"{ticker}: OPERATE_COST should be null for financial stock, got {result}"
    )


@pytest.mark.parametrize("ticker,year", FINANCIAL_STOCKS)
def test_financial_operate_profit_present(ticker: str, year: int) -> None:
    """Financial stocks have OPERATE_PROFIT field populated.

    OPERATE_PROFIT is used by the financial NOPAT formula.
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _coalesce_akshare_field(income, "OPERATE_PROFIT")
    assert result is not None, (
        f"{ticker}: OPERATE_PROFIT should be present for financial stock"
    )
    assert float(result) != 0.0, f"{ticker}: OPERATE_PROFIT is zero"


@pytest.mark.parametrize("ticker,year", FINANCIAL_STOCKS)
def test_financial_cost_of_goods_uses_fallback(ticker: str, year: int) -> None:
    """Financial stocks use OPERATE_EXPENSE fallback for cost_of_goods.

    Since OPERATE_COST is null, _extract_akshare_cost_of_goods falls back
    to OPERATE_EXPENSE for financial stocks.
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _extract_akshare_cost_of_goods(income)
    assert result != "0", (
        f"{ticker}: cost_of_goods should use OPERATE_EXPENSE fallback, got '0'"
    )
    assert float(result) != 0.0, (
        f"{ticker}: cost_of_goods fallback value should be non-zero"
    )


@pytest.mark.parametrize("ticker,year", FINANCIAL_STOCKS)
def test_financial_insurance_income_or_operate_income(ticker: str, year: int) -> None:
    """Financial stocks have either OPERATE_INCOME or INSURANCE_INCOME.

    Banking stocks have OPERATE_INCOME; insurance stocks have INSURANCE_INCOME.
    This triggers the financial-sector fallback in _extract_akshare_cost_of_goods.
    """
    income = _load_frozen_json(ticker, year, "income")
    org_type = str(income.get("ORG_TYPE", ""))

    if "\u94f6\u884c" in org_type:
        # Banking: OPERATE_INCOME should be populated
        result = _coalesce_akshare_field(income, "OPERATE_INCOME")
        assert result is not None, (
            f"{ticker}: OPERATE_INCOME should be present for banking stock"
        )
    elif "\u4fdd\u9669" in org_type:
        # Insurance: INSURANCE_INCOME should be populated
        result = _coalesce_akshare_field(income, "INSURANCE_INCOME")
        assert result is not None, (
            f"{ticker}: INSURANCE_INCOME should be present for insurance stock"
        )
    else:
        pytest.skip(f"{ticker}: not a standard banking/insurance stock")


# ===================================================================
# Non-financial stock field extraction tests (parametrized)
# ===================================================================


@pytest.mark.parametrize("ticker,year", NON_FINANCIAL_STOCKS)
def test_non_financial_operate_cost_present(ticker: str, year: int) -> None:
    """Non-financial stocks have OPERATE_COST field populated and non-zero.

    Standard manufacturing/service companies report cost of goods sold.
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _coalesce_akshare_field(income, "OPERATE_COST")
    assert result is not None, (
        f"{ticker}: OPERATE_COST should be present for non-financial stock"
    )
    assert float(result) != 0.0, (
        f"{ticker}: OPERATE_COST should be non-zero for non-financial stock"
    )


@pytest.mark.parametrize("ticker,year", NON_FINANCIAL_STOCKS)
def test_non_financial_finance_expense_present(ticker: str, year: int) -> None:
    """Non-financial stocks have FINANCE_EXPENSE field populated.

    FINANCE_EXPENSE is required for the non-financial NOPAT formula:
    NOPAT = (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate).
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _coalesce_akshare_field(income, "FINANCE_EXPENSE")
    assert result is not None, (
        f"{ticker}: FINANCE_EXPENSE should be present for non-financial stock"
    )


@pytest.mark.parametrize("ticker,year", NON_FINANCIAL_STOCKS)
def test_non_financial_cost_of_goods_standard(ticker: str, year: int) -> None:
    """Non-financial stocks use standard OPERATE_COST for cost_of_goods.

    The extraction should return the OPERATE_COST value directly, not the
    OPERATE_EXPENSE fallback.
    """
    income = _load_frozen_json(ticker, year, "income")
    cost_of_goods = _extract_akshare_cost_of_goods(income)
    operate_cost = _coalesce_akshare_field(income, "OPERATE_COST")

    assert operate_cost is not None, f"{ticker}: OPERATE_COST missing"
    assert cost_of_goods == str(operate_cost), (
        f"{ticker}: cost_of_goods ({cost_of_goods}) does not match "
        f"OPERATE_COST ({operate_cost}) -- fallback path triggered incorrectly"
    )


# ===================================================================
# NOPAT formula branch tests (specific stocks)
# ===================================================================


def test_nopat_financial_formula() -> None:
    """Financial NOPAT uses OPERATE_PROFIT * (1 - tax_rate).

    Uses frozen income data for 601398.SH (ICBC, banking).
    """
    income = _load_frozen_json("601398.SH", 2023, "income")
    operate_profit = float(_coalesce_akshare_field(income, "OPERATE_PROFIT") or 0)
    income_tax = float(_coalesce_akshare_field(income, "INCOME_TAX") or 0)
    total_profit = float(_coalesce_akshare_field(income, "TOTAL_PROFIT") or 0)

    profit_data = {
        "OPERATE_PROFIT": operate_profit,
        "INCOME_TAX": income_tax,
        "TOTAL_PROFIT": total_profit,
    }

    nopat, audit_trail = calculate_nopat(profit_data, is_financial=True)

    assert nopat is not None, "Financial NOPAT should not be None"
    assert nopat > 0, f"Financial NOPAT should be positive, got {nopat}"
    assert audit_trail["formula"] == "OPERATE_PROFIT * (1 - tax_rate)", (
        f"Unexpected formula: {audit_trail['formula']}"
    )
    assert "FINANCE_EXPENSE" not in audit_trail["formula"], (
        "Financial formula should not include FINANCE_EXPENSE"
    )


def test_nopat_non_financial_formula() -> None:
    """Non-financial NOPAT uses (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate).

    Uses frozen income data for 600519.SH (Kweichow Moutai, consumer).
    """
    income = _load_frozen_json("600519.SH", 2023, "income")
    total_profit = float(_coalesce_akshare_field(income, "TOTAL_PROFIT") or 0)
    finance_expense = float(_coalesce_akshare_field(income, "FINANCE_EXPENSE") or 0)
    income_tax = float(_coalesce_akshare_field(income, "INCOME_TAX") or 0)

    profit_data = {
        "TOTAL_PROFIT": total_profit,
        "FINANCE_EXPENSE": finance_expense,
        "INCOME_TAX": income_tax,
    }

    nopat, audit_trail = calculate_nopat(profit_data, is_financial=False)

    assert nopat is not None, "Non-financial NOPAT should not be None"
    assert nopat > 0, f"Non-financial NOPAT should be positive, got {nopat}"
    assert (
        audit_trail["formula"] == "(TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)"
    ), f"Unexpected formula: {audit_trail['formula']}"


def test_nopat_branches_produce_different_results() -> None:
    """Financial and non-financial NOPAT formulas produce different results.

    When the same data contains both OPERATE_PROFIT and TOTAL_PROFIT,
    the two branch formulas should yield different NOPAT values, verifying
    that the branch logic actually diverges.
    """
    income = _load_frozen_json("600519.SH", 2023, "income")
    operate_profit = float(_coalesce_akshare_field(income, "OPERATE_PROFIT") or 0)
    total_profit = float(_coalesce_akshare_field(income, "TOTAL_PROFIT") or 0)
    finance_expense = float(_coalesce_akshare_field(income, "FINANCE_EXPENSE") or 0)
    income_tax = float(_coalesce_akshare_field(income, "INCOME_TAX") or 0)

    # Input dict has both OPERATE_PROFIT and TOTAL_PROFIT + FINANCE_EXPENSE
    profit_data = {
        "OPERATE_PROFIT": operate_profit,
        "TOTAL_PROFIT": total_profit,
        "FINANCE_EXPENSE": finance_expense,
        "INCOME_TAX": income_tax,
    }

    nopat_fin, _ = calculate_nopat(profit_data, is_financial=True)
    nopat_nonfin, _ = calculate_nopat(profit_data, is_financial=False)

    assert nopat_fin is not None, "Financial NOPAT should not be None"
    assert nopat_nonfin is not None, "Non-financial NOPAT should not be None"
    assert nopat_fin != nopat_nonfin, (
        f"Financial ({nopat_fin}) and non-financial ({nopat_nonfin}) NOPAT "
        f"should differ for the same input data -- branch logic may not diverge"
    )


def test_financial_nopat_no_finance_expense_used() -> None:
    """Financial NOPAT formula does not use FINANCE_EXPENSE.

    For 601398.SH (banking), the financial NOPAT should use OPERATE_PROFIT
    and not include FINANCE_EXPENSE in the formula or inputs.
    """
    income = _load_frozen_json("601398.SH", 2023, "income")
    operate_profit = float(_coalesce_akshare_field(income, "OPERATE_PROFIT") or 0)
    income_tax = float(_coalesce_akshare_field(income, "INCOME_TAX") or 0)
    total_profit = float(_coalesce_akshare_field(income, "TOTAL_PROFIT") or 0)

    profit_data = {
        "OPERATE_PROFIT": operate_profit,
        "INCOME_TAX": income_tax,
        "TOTAL_PROFIT": total_profit,
    }

    nopat, audit_trail = calculate_nopat(profit_data, is_financial=True)

    assert nopat is not None
    assert "FINANCE_EXPENSE" not in audit_trail["formula"], (
        "Financial NOPAT formula should not reference FINANCE_EXPENSE"
    )
    # Inputs should also not include FINANCE_EXPENSE
    assert "FINANCE_EXPENSE" not in audit_trail.get("inputs", {}), (
        "Financial NOPAT inputs should not include FINANCE_EXPENSE"
    )
