"""L2 field mapping verification: snapshot tests and traceability tests.

Snapshot tests (LV2-01):
    Verify that AKShare field extraction functions produce non-null values
    for all key financial fields across all 14 golden stocks.

Traceability tests (LV2-02):
    Verify that IndexAuditDetail numerator/denominator values are internally
    consistent with computed sub-index values for the anchor stock 600519.SH.

All tests are marked ``@pytest.mark.l2_mapping`` and require no network
access -- they read frozen AKShare JSON files from the golden dataset.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from stockvaluefinder.external.data_service import (  # type: ignore[attr-defined]
    _coalesce_akshare_field,
    _extract_akshare_accounts_receivable,
    _extract_akshare_cost_of_goods,
    _extract_akshare_revenue,
    _extract_akshare_sga_expense,
)
from stockvaluefinder.services.risk_service import calculate_mscore_indices
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


# ===================================================================
# SNAPSHOT TESTS -- parametrized across all 14 golden stocks (LV2-01)
# ===================================================================


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_revenue_extraction(ticker: str, year: int) -> None:
    """Revenue extraction returns non-null, non-zero string."""
    income = _load_frozen_json(ticker, year, "income")
    result = _extract_akshare_revenue(income)
    assert result is not None, f"{ticker}: revenue extraction returned None"
    assert float(result) != 0.0, f"{ticker}: revenue is zero"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_cost_of_goods_extraction(ticker: str, year: int) -> None:
    """Cost of goods extraction returns non-null string.

    For financial stocks, the value may be from the OPERATE_EXPENSE fallback
    path.  Both financial and non-financial stocks must produce a non-None
    result, and for non-financial stocks it should be non-zero.
    """
    income = _load_frozen_json(ticker, year, "income")
    result = _extract_akshare_cost_of_goods(income)
    assert result is not None, f"{ticker}: cost_of_goods extraction returned None"
    if not _is_financial(ticker):
        assert float(result) != 0.0, f"{ticker}: non-financial cost_of_goods is zero"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_sga_expense_extraction(ticker: str, year: int) -> None:
    """SGA expense extraction returns non-zero for non-financial stocks."""
    income = _load_frozen_json(ticker, year, "income")
    result = _extract_akshare_sga_expense(income)
    assert result is not None, f"{ticker}: sga_expense extraction returned None"
    # Financial stocks may legitimately have no TOTAL_OPERATE_COST; skip them
    if not _is_financial(ticker):
        assert float(result) != 0.0, f"{ticker}: non-financial sga_expense is zero"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_accounts_receivable_extraction(ticker: str, year: int) -> None:
    """Accounts receivable extraction returns non-null string."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _extract_akshare_accounts_receivable(balance)
    assert result is not None, f"{ticker}: accounts_receivable extraction returned None"
    # Banking stocks may have zero AR (use PREMIUM_RECE/NOTE_RECE fallback)
    if not _is_financial(ticker):
        assert float(result) != 0.0, (
            f"{ticker}: non-financial accounts_receivable is zero"
        )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_netprofit_present(ticker: str, year: int) -> None:
    """NETPROFIT is present and non-zero after coalescing."""
    income = _load_frozen_json(ticker, year, "income")
    result = _coalesce_akshare_field(income, "NETPROFIT")
    assert result is not None, f"{ticker}: NETPROFIT is None"
    assert float(result) != 0.0, f"{ticker}: NETPROFIT is zero"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_netcash_operate_present(ticker: str, year: int) -> None:
    """NETCASH_OPERATE is present after coalescing."""
    cashflow = _load_frozen_json(ticker, year, "cashflow")
    result = _coalesce_akshare_field(cashflow, "NETCASH_OPERATE")
    assert result is not None, f"{ticker}: NETCASH_OPERATE is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_assets_present(ticker: str, year: int) -> None:
    """TOTAL_ASSETS is present after coalescing."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "TOTAL_ASSETS")
    assert result is not None, f"{ticker}: TOTAL_ASSETS is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_liabilities_present(ticker: str, year: int) -> None:
    """TOTAL_LIABILITIES is present after coalescing."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "TOTAL_LIABILITIES")
    assert result is not None, f"{ticker}: TOTAL_LIABILITIES is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_monetaryfunds_present(ticker: str, year: int) -> None:
    """MONETARYFUNDS is present after coalescing.

    Banking stocks may not populate MONETARYFUNDS (they use different
    balance sheet categories), so we only assert for non-financial stocks.
    """
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "MONETARYFUNDS")
    if not _is_financial(ticker):
        assert result is not None, f"{ticker}: MONETARYFUNDS is None (non-financial)"
    else:
        # Financial stocks: MONETARYFUNDS may be None -- acceptable
        pass


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_equity_present(ticker: str, year: int) -> None:
    """TOTAL_EQUITY is present after coalescing."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "TOTAL_EQUITY")
    assert result is not None, f"{ticker}: TOTAL_EQUITY is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_current_assets_present(ticker: str, year: int) -> None:
    """TOTAL_CURRENT_ASSETS is present after coalescing for non-financial stocks.

    Banking/insurance stocks often do not report TOTAL_CURRENT_ASSETS.
    """
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "TOTAL_CURRENT_ASSETS")
    if not _is_financial(ticker):
        assert result is not None, (
            f"{ticker}: TOTAL_CURRENT_ASSETS is None (non-financial)"
        )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_fixed_asset_present(ticker: str, year: int) -> None:
    """FIXED_ASSET is present after coalescing."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "FIXED_ASSET")
    assert result is not None, f"{ticker}: FIXED_ASSET is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_total_parent_equity_present(ticker: str, year: int) -> None:
    """TOTAL_PARENT_EQUITY is present after coalescing."""
    balance = _load_frozen_json(ticker, year, "balance")
    result = _coalesce_akshare_field(balance, "TOTAL_PARENT_EQUITY")
    assert result is not None, f"{ticker}: TOTAL_PARENT_EQUITY is None"


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_standardized_report_mscore_fields(ticker: str, year: int) -> None:
    """Standardized report has all M-Score required fields as non-zero floats.

    Financial stocks have exemptions for fields that are structurally zero
    (e.g., sga_expense, accounts_receivable, total_current_assets).
    """
    income = _load_frozen_json(ticker, year, "income")
    balance = _load_frozen_json(ticker, year, "balance")
    cashflow = _load_frozen_json(ticker, year, "cashflow")
    report = build_standardized_report_from_frozen(
        income, balance, cashflow, ticker, year
    )

    # Core fields that must be non-zero for ALL stocks
    core_fields = [
        "revenue",
        "net_income",
        "operating_cash_flow",
        "cost_of_goods",
        "total_liabilities",
    ]
    for field in core_fields:
        val = report.get(field, "0")
        assert float(val) != 0.0, f"{ticker}: report.{field} is zero"

    # Assets must be non-zero
    assets_val = report.get("assets_total", report.get("total_assets", "0"))
    assert float(assets_val) != 0.0, f"{ticker}: report.assets_total is zero"

    # Fields exempted for financial stocks
    if not _is_financial(ticker):
        exempt_fields = [
            "accounts_receivable",
            "total_current_assets",
            "ppe",
            "sga_expense",
        ]
        for field in exempt_fields:
            val = report.get(field, "0")
            assert float(val) != 0.0, (
                f"{ticker}: report.{field} is zero (non-financial)"
            )


@pytest.mark.parametrize("ticker,year", ALL_STOCK_IDS)
def test_roic_profit_fields(ticker: str, year: int) -> None:
    """ROIC input fields TOTAL_PROFIT and INCOME_TAX are present and non-zero."""
    income = _load_frozen_json(ticker, year, "income")

    total_profit = _coalesce_akshare_field(income, "TOTAL_PROFIT")
    assert total_profit is not None, f"{ticker}: TOTAL_PROFIT is None"
    assert float(total_profit) != 0.0, f"{ticker}: TOTAL_PROFIT is zero"

    income_tax = _coalesce_akshare_field(income, "INCOME_TAX")
    assert income_tax is not None, f"{ticker}: INCOME_TAX is None"


# =================================================================
# TRACEABILITY TESTS -- anchor stock 600519.SH only (LV2-02)
# =================================================================


class TestMscoreIndexTraceability:
    """Verify IndexAuditDetail consistency for anchor stock 600519.SH.

    Uses frozen 2023 data as the current report. A synthetic previous
    report is created by multiplying all float fields by 0.95, since
    only one year of frozen data exists per stock.
    """

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Load frozen data and compute M-Score indices for 600519.SH."""
        ticker = "600519.SH"
        year = 2023
        self.ticker = ticker

        income = _load_frozen_json(ticker, year, "income")
        balance = _load_frozen_json(ticker, year, "balance")
        cashflow = _load_frozen_json(ticker, year, "cashflow")

        self.current_report = build_standardized_report_from_frozen(
            income, balance, cashflow, ticker, year
        )

        # Synthetic previous: multiply all numeric fields by 0.95
        self.previous_report = {
            k: (
                _scale_float(v, 0.95)
                if isinstance(v, (int, float, str))
                and k != "ticker"
                and k != "report_source"
                else v
            )
            for k, v in self.current_report.items()
        }
        # Preserve string-type fields that should remain strings
        for k in ("ticker", "report_id", "period", "report_type", "report_source"):
            if k in self.previous_report:
                self.previous_report[k] = self.current_report[k]

        self.result = calculate_mscore_indices(
            self.current_report,
            self.previous_report,
            source_name="AKShare",
        )
        self.audit_trail = self.result["audit_trail"]

    def test_audit_trail_has_all_8_indices(self) -> None:
        """Audit trail contains all 8 M-Score sub-indices."""
        expected_keys = {"dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"}
        actual_keys = set(self.audit_trail.keys())
        assert actual_keys == expected_keys, (
            f"Missing: {expected_keys - actual_keys}, Extra: {actual_keys - expected_keys}"
        )

    def test_numerator_denominator_consistency(self) -> None:
        """For each non-DEPI index: numerator/denominator matches value within 0.001."""
        for index_name in ["dsri", "gmi", "aqi", "sgi", "sgai", "lvgi", "tata"]:
            detail = self.audit_trail[index_name]
            if detail.denominator != 0:
                recomputed = detail.numerator / detail.denominator
                assert abs(recomputed - detail.value) < 0.001, (
                    f"{index_name}: numerator/denominator={recomputed:.4f} "
                    f"!= value={detail.value:.4f}"
                )

    def test_tata_traceability(self) -> None:
        """TATA numerator equals (net_income - operating_cash_flow), denominator equals assets_total."""
        detail = self.audit_trail["tata"]
        ni = float(self.current_report["net_income"])
        ocf = float(self.current_report["operating_cash_flow"])
        assets = float(self.current_report["assets_total"])

        expected_numerator = ni - ocf
        assert (
            abs(detail.numerator - expected_numerator) / max(abs(expected_numerator), 1)
            < 0.01
        ), (
            f"TATA numerator: got {detail.numerator:.2f}, expected {expected_numerator:.2f}"
        )
        assert abs(detail.denominator - assets) / max(abs(assets), 1) < 0.01, (
            f"TATA denominator: got {detail.denominator:.2f}, expected {assets:.2f}"
        )

    def test_sgi_traceability(self) -> None:
        """SGI numerator equals current revenue, denominator equals previous revenue."""
        detail = self.audit_trail["sgi"]
        curr_rev = float(self.current_report["revenue"])
        prev_rev = float(self.previous_report["revenue"])

        assert abs(detail.numerator - curr_rev) / max(abs(curr_rev), 1) < 0.01, (
            f"SGI numerator: got {detail.numerator:.2f}, expected {curr_rev:.2f}"
        )
        assert abs(detail.denominator - prev_rev) / max(abs(prev_rev), 1) < 0.01, (
            f"SGI denominator: got {detail.denominator:.2f}, expected {prev_rev:.2f}"
        )

    def test_source_fields_populated(self) -> None:
        """Each non-DEPI index has source_fields with at least 1 entry."""
        for index_name in ["dsri", "gmi", "aqi", "sgi", "sgai", "lvgi", "tata"]:
            detail = self.audit_trail[index_name]
            assert len(detail.source_fields) >= 1, (
                f"{index_name}: source_fields is empty"
            )

    def test_depi_mvp_hardcoded(self) -> None:
        """DEPI is hardcoded to 1.0 with MVP reason."""
        depi = self.audit_trail["depi"]
        assert depi.value == 1.0, f"DEPI value: got {depi.value}, expected 1.0"
        assert "MVP" in (depi.reason or ""), f"DEPI reason: got '{depi.reason}'"
        assert depi.non_calculable is False, "DEPI should not be non_calculable"

    def test_all_indices_finite_and_reasonable(self) -> None:
        """All index values are finite and in reasonable range (-10, 100)."""
        for index_name in ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]:
            val = self.result[index_name]
            assert math.isfinite(val), f"{index_name}: value is not finite: {val}"
            assert -10 < val < 100, (
                f"{index_name}: value {val} outside range (-10, 100)"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scale_float(value: Any, factor: float) -> Any:
    """Scale a numeric value (int/float/str-representable) by factor.

    Returns the scaled value as a string if the input was a string,
    otherwise as a float.  Non-numeric inputs are returned unchanged.
    """
    if isinstance(value, str):
        try:
            num = float(value)
            return str(num * factor)
        except (ValueError, TypeError):
            return value
    if isinstance(value, (int, float)):
        return value * factor
    return value
