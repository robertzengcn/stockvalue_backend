"""Pytest fixtures and helpers for L2 field mapping verification tests.

Provides:
- frozen_akshare_data: Session-scoped fixture returning a callable to load
  frozen AKShare JSON for any golden stock (income/balance/cashflow).
- build_standardized_report_from_frozen: Helper function that replicates
  the AKShare report building logic from data_service.py using frozen JSON.
- roic_inputs_from_frozen: Helper that extracts ROIC-relevant fields from
  frozen income and balance records.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from stockvaluefinder.external.data_service import (  # type: ignore[attr-defined]
    _coalesce_akshare_field,
    _extract_akshare_accounts_receivable,
    _extract_akshare_cost_of_goods,
    _extract_akshare_revenue,
    _extract_akshare_sga_expense,
)


GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden"


def _sanitize_nan(obj: Any) -> Any:
    """Walk a data structure and replace NaN/Inf floats with None.

    The frozen AKShare JSON files contain NaN float values (Python's
    ``json.loads`` parses them as ``float('nan')``).  This helper
    ensures they do not silently propagate through calculations.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(item) for item in obj]
    return obj


def _load_frozen_json(ticker: str, year: int, statement: str) -> dict[str, Any]:
    """Load a frozen AKShare JSON file and return the first record.

    Args:
        ticker: Stock ticker (e.g. ``600519.SH``).
        year: Fiscal year (e.g. ``2023``).
        statement: One of ``income``, ``balance``, ``cashflow``.

    Returns:
        First record dict from the frozen file with NaN values replaced
        by ``None``.

    Raises:
        FileNotFoundError: If the frozen JSON file does not exist.
    """
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
    return _sanitize_nan(records[0])


@pytest.fixture(scope="session")
def frozen_akshare_data() -> Any:
    """Return a callable that loads frozen AKShare data for a ticker/year.

    Returns:
        Callable accepting ``(ticker, year)`` and returning dict with keys
        ``income``, ``balance``, ``cashflow`` (each a dict of field->value).
    """
    cache: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}

    def _load(ticker: str, year: int) -> dict[str, dict[str, Any]]:
        key = (ticker, year)
        if key in cache:
            return cache[key]
        result = {
            "income": _load_frozen_json(ticker, year, "income"),
            "balance": _load_frozen_json(ticker, year, "balance"),
            "cashflow": _load_frozen_json(ticker, year, "cashflow"),
        }
        cache[key] = result
        return result

    return _load


def build_standardized_report_from_frozen(
    income: dict[str, Any],
    balance: dict[str, Any],
    cashflow: dict[str, Any],
    ticker: str,
    year: int = 2023,
) -> dict[str, Any]:
    """Replicate the AKShare report building logic from data_service.py.

    Uses the same ``_extract_akshare_*`` and ``_coalesce_akshare_field``
    functions as the production code, but operates on frozen JSON data
    instead of live AKShare API responses.

    Args:
        income: Frozen income statement record (first record from JSON).
        balance: Frozen balance sheet record.
        cashflow: Frozen cashflow statement record.
        ticker: Stock ticker (e.g. ``600519.SH``).
        year: Fiscal year.

    Returns:
        Standardized financial report dict matching the structure produced
        by ``ExternalDataService._get_financial_report_from_akshare``.
    """
    # Gross margin calculation (replicating _calculate_gross_margin_from_akshare)
    revenue_raw = _coalesce_akshare_field(
        income,
        "TOTAL_OPERATE_INCOME",
        "OPERATE_INCOME",
        "INSURANCE_INCOME",
        "\u8425\u4e1a\u603b\u6536\u5165",
        "\u8425\u4e1a\u6536\u5165",
    )
    revenue = float(revenue_raw) if revenue_raw is not None else 0.0

    cost_raw = _coalesce_akshare_field(
        income, "OPERATE_COST", "\u8425\u4e1a\u6210\u672c"
    )
    if (
        cost_raw is None
        and _coalesce_akshare_field(income, "OPERATE_INCOME", "INSURANCE_INCOME")
        is not None
    ):
        cost_raw = _coalesce_akshare_field(
            income, "OPERATE_EXPENSE", "\u8425\u4e1a\u603b\u6210\u672c"
        )
    cost = float(cost_raw) if cost_raw is not None else 0.0

    if revenue > 0:
        gross_margin = round(((revenue - cost) / revenue) * 100, 2)
    else:
        gross_margin = 0.0

    def _field_str(
        record: dict[str, Any],
        *keys: str,
        default: str = "0",
    ) -> str:
        """Return first non-None value from *keys* as string, or *default*."""
        for key in keys:
            if key in record and record[key] is not None:
                return str(record[key])
        return default

    report: dict[str, Any] = {
        "ticker": ticker,
        "report_id": uuid4(),
        "period": f"{year}-12-31",
        "report_type": "ANNUAL",
        "fiscal_year": year,
        "fiscal_quarter": None,
        # Income statement
        "revenue": _extract_akshare_revenue(income),
        "net_income": _field_str(
            income,
            "NETPROFIT",
            "\u51c0\u5229\u6da6",
            "\u5f52\u5c5e\u6bcd\u516c\u53f8\u6240\u6709\u8005\u7684\u51c0\u5229\u6da6",
        ),
        "operating_cash_flow": _field_str(
            cashflow,
            "NETCASH_OPERATE",
            "\u7ecf\u8425\u6d3b\u52a8\u4ea7\u751f\u7684\u73b0\u91d1\u6d41\u91cf\u51c0\u989d",
        ),
        "gross_margin": gross_margin,
        # Balance sheet
        "assets_total": _field_str(balance, "TOTAL_ASSETS", "\u8d44\u4ea7\u603b\u8ba1"),
        "liabilities_total": _field_str(
            balance, "TOTAL_LIABILITIES", "\u8d1f\u503a\u5408\u8ba1"
        ),
        "equity_total": _field_str(
            balance, "TOTAL_EQUITY", "\u6240\u6709\u8005\u6743\u76ca\u5408\u8ba1"
        ),
        "accounts_receivable": _extract_akshare_accounts_receivable(balance),
        "inventory": _field_str(balance, "INVENTORY", "\u5b58\u8d27"),
        "fixed_assets": _field_str(balance, "FIXED_ASSET", "\u56fa\u5b9a\u8d44\u4ea7"),
        "goodwill": _field_str(balance, "GOODWILL", "\u5546\u8a89"),
        "cash_and_equivalents": _field_str(
            balance, "MONETARYFUNDS", "\u8d27\u5e01\u8d44\u91d1"
        ),
        "interest_bearing_debt": _field_str(
            balance, "TOTAL_LIABILITIES", "\u8d1f\u503a\u5408\u8ba1"
        ),
        # M-Score raw financial fields
        "cost_of_goods": _extract_akshare_cost_of_goods(income),
        "sga_expense": _extract_akshare_sga_expense(income),
        "total_current_assets": _field_str(
            balance, "TOTAL_CURRENT_ASSETS", "\u6d41\u52a8\u8d44\u4ea7\u5408\u8ba1"
        ),
        "ppe": _field_str(balance, "FIXED_ASSET", "\u56fa\u5b9a\u8d44\u4ea7"),
        "long_term_debt": _field_str(balance, "LONG_LOAN", "\u957f\u671f\u501f\u6b3e"),
        "total_liabilities": _field_str(
            balance, "TOTAL_LIABILITIES", "\u8d1f\u503a\u5408\u8ba1"
        ),
        "report_source": "AKShare(frozen)",
    }

    return report


def roic_inputs_from_frozen(
    income: dict[str, Any],
    balance: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract ROIC-relevant fields from frozen income and balance records.

    Returns a dict with ``profit`` and ``balance`` sub-dicts matching the
    structure expected by ``get_roic_inputs`` from data_service.py.

    Args:
        income: Frozen income statement record.
        balance: Frozen balance sheet record.

    Returns:
        Dict with ``profit`` (TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX,
        OPERATE_PROFIT, NETPROFIT) and ``balance`` (TOTAL_PARENT_EQUITY,
        SHORT_LOAN, LONG_LOAN, BOND_PAYABLE, TREASURY_SHARES,
        TOTAL_ASSETS, TOTAL_LIABILITIES, MONETARYFUNDS) sub-dicts.
    """
    profit_keys = [
        "TOTAL_PROFIT",
        "FINANCE_EXPENSE",
        "INCOME_TAX",
        "OPERATE_PROFIT",
        "NETPROFIT",
    ]
    balance_keys = [
        "TOTAL_PARENT_EQUITY",
        "SHORT_LOAN",
        "LONG_LOAN",
        "BOND_PAYABLE",
        "TREASURY_SHARES",
        "TOTAL_ASSETS",
        "TOTAL_LIABILITIES",
        "MONETARYFUNDS",
    ]
    profit = {k: income.get(k) for k in profit_keys}
    bal = {k: balance.get(k) for k in balance_keys}
    return {"profit": profit, "balance": bal}
