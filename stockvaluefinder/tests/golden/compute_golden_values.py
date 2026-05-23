"""Compute golden values for a frozen golden stock from frozen AKShare data.

This script loads the frozen AKShare JSON for a given ticker/year pair,
transforms it into the same standardized dict format used by data_service.py,
then calls the production calculate_* functions to compute exact golden values.

The output is written to expected_metrics.yaml and (optionally) provenance.md.

Usage::

    uv run python tests/golden/compute_golden_values.py --ticker 600519.SH --year 2023
    uv run python tests/golden/compute_golden_values.py --ticker 601398.SH --year 2023
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
GOLDEN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GOLDEN_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Replicate private field extraction functions from data_service.py
# to avoid importing private symbols that fail mypy's attr-defined check.
# These are identical to the originals -- single source of truth is data_service.py.


def _coalesce_akshare_field(record: dict[str, Any], *keys: str) -> Any | None:
    """Return the first present, non-null, non-NaN value for any of *keys."""
    for key in keys:
        if key not in record:
            continue
        val = record[key]
        if val is None:
            continue
        try:
            if float(val) != float(val):  # NaN
                continue
        except (ValueError, TypeError):
            continue
        return val
    return None


def _extract_akshare_revenue(income: dict[str, Any]) -> str:
    """Map income statement to standardized revenue."""
    val = _coalesce_akshare_field(
        income,
        "TOTAL_OPERATE_INCOME",
        "OPERATE_INCOME",
        "INSURANCE_INCOME",
        "营业总收入",
        "营业收入",
    )
    return str(val) if val is not None else "0"


def _extract_akshare_cost_of_goods(income: dict[str, Any]) -> str:
    """Map income statement to standardized cost of goods sold."""
    cost = _coalesce_akshare_field(income, "OPERATE_COST", "营业成本")
    if cost is not None:
        return str(cost)
    if (
        _coalesce_akshare_field(income, "OPERATE_INCOME", "INSURANCE_INCOME")
        is not None
    ):
        expense = _coalesce_akshare_field(income, "OPERATE_EXPENSE", "营业总成本")
        if expense is not None:
            return str(expense)
    return "0"


def _extract_akshare_sga_expense(income: dict[str, Any]) -> str:
    """Map income statement to standardized SGA expense."""
    val = _coalesce_akshare_field(income, "TOTAL_OPERATE_COST", "营业总成本")
    return str(val) if val is not None else "0"


def _extract_akshare_accounts_receivable(balance: dict[str, Any]) -> str:
    """Map balance sheet to standardized accounts receivable."""
    val = _coalesce_akshare_field(
        balance,
        "ACCOUNTS_RECE",
        "PREMIUM_RECE",
        "FINANCE_RECE",
        "NOTE_RECE",
        "应收账款",
    )
    return str(val) if val is not None else "0"


from stockvaluefinder.services.risk_service import (  # noqa: E402
    calculate_beneish_m_score,
    calculate_goodwill_ratio,
    calculate_mscore_indices,
    calculate_piotroski_f_score,
    detect_profit_cash_divergence,
    detect_存贷双高,
)
from stockvaluefinder.services.roic_service import (  # noqa: E402
    calculate_invested_capital,
    calculate_nopat,
    calculate_roic,
)
import yaml  # type: ignore[import-untyped]  # noqa: E402


def lookup_is_financial(ticker: str) -> bool:
    """Check if a ticker is in the financial sector per the golden manifest.

    Args:
        ticker: Stock ticker (e.g. ``"601398.SH"``).

    Returns:
        ``True`` if ``is_financial`` is set in the manifest entry,
        ``False`` otherwise (including when ticker is not found).
    """
    manifest_path = GOLDEN_DIR / "manifest.yaml"
    content = manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(content)
    for entry in manifest["golden_stocks"]:
        if entry["ticker"] == ticker:
            return bool(entry.get("is_financial", False))
    return False


def load_frozen_records(filepath: Path) -> list[dict[str, Any]]:
    """Load records from a frozen AKShare JSON file.

    Args:
        filepath: Path to the frozen JSON file.

    Returns:
        List of record dicts from the frozen file.
    """
    data = json.loads(filepath.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    return data


def find_record_for_period(
    records: list[dict[str, Any]], year: int
) -> dict[str, Any] | None:
    """Find the record matching a specific fiscal year end (YYYY-12-31).

    Args:
        records: List of AKShare records.
        year: Fiscal year to find.

    Returns:
        Matching record dict, or None.
    """
    period_str = f"{year}-12-31"
    period_nodash = f"{year}1231"
    for r in records:
        rd = str(r.get("REPORT_DATE", ""))
        if period_str in rd or period_nodash in rd:
            return r
    return None


def build_standardized_report(
    income: dict[str, Any],
    balance: dict[str, Any],
    cashflow: dict[str, Any],
    ticker: str,
    year: int,
) -> dict[str, Any]:
    """Build a standardized report dict from frozen AKShare data.

    Uses the same field extraction functions as data_service.py
    to ensure identical mapping.

    Args:
        income: Income statement record from AKShare.
        balance: Balance sheet record from AKShare.
        cashflow: Cash flow record from AKShare.
        ticker: Stock ticker string.
        year: Fiscal year.

    Returns:
        Standardized financial report dictionary.
    """

    # Helper for float field extraction (matches data_service behavior)
    def _field_str(record: dict[str, Any], *keys: str, default: str = "0") -> str:
        val = _coalesce_akshare_field(record, *keys)
        return str(val) if val is not None else default

    revenue = _extract_akshare_revenue(income)
    net_income = _field_str(income, "NETPROFIT", "净利润", "归属母公司所有者的净利润")
    operating_cash_flow = _field_str(
        cashflow, "NETCASH_OPERATE", "经营活动产生的现金流量净额"
    )

    # Calculate gross margin
    rev_f = float(revenue)
    cogs = float(_extract_akshare_cost_of_goods(income))
    gross_margin = (rev_f - cogs) / rev_f if rev_f != 0 else 0.0

    return {
        "ticker": ticker,
        "fiscal_year": year,
        "period": f"{year}-12-31",
        # Income statement
        "revenue": revenue,
        "net_income": net_income,
        "operating_cash_flow": operating_cash_flow,
        "gross_margin": gross_margin,
        # Balance sheet
        "assets_total": _field_str(balance, "TOTAL_ASSETS", "资产总计"),
        "liabilities_total": _field_str(balance, "TOTAL_LIABILITIES", "负债合计"),
        "equity_total": _field_str(balance, "TOTAL_EQUITY", "所有者权益合计"),
        "accounts_receivable": _extract_akshare_accounts_receivable(balance),
        "cash_and_equivalents": _field_str(balance, "MONETARYFUNDS", "货币资金"),
        "interest_bearing_debt": _field_str(balance, "TOTAL_LIABILITIES", "负债合计"),
        "goodwill": _field_str(balance, "GOODWILL", "商誉"),
        # M-Score raw financial fields
        "cost_of_goods": _extract_akshare_cost_of_goods(income),
        "sga_expense": _extract_akshare_sga_expense(income),
        "total_current_assets": _field_str(
            balance, "TOTAL_CURRENT_ASSETS", "流动资产合计"
        ),
        "ppe": _field_str(balance, "FIXED_ASSET", "固定资产"),
        "total_assets": _field_str(balance, "TOTAL_ASSETS", "资产总计"),
        "total_liabilities": _field_str(balance, "TOTAL_LIABILITIES", "负债合计"),
        "long_term_debt": _field_str(balance, "LONG_LOAN", "长期借款"),
        # F-Score fields
        "shares_outstanding": "0",  # Not in AKShare financial statements
        # ROIC fields (from balance sheet)
        "TOTAL_PARENT_EQUITY": _field_str(balance, "TOTAL_PARENT_EQUITY"),
        "SHORT_LOAN": _field_str(balance, "SHORT_LOAN"),
        "LONG_LOAN": _field_str(balance, "LONG_LOAN"),
        "BOND_PAYABLE": _field_str(balance, "BOND_PAYABLE"),
        "TREASURY_SHARES": _field_str(balance, "TREASURY_SHARES"),
        # ROIC fields (from income statement)
        "TOTAL_PROFIT": _field_str(income, "TOTAL_PROFIT"),
        "FINANCE_EXPENSE": _field_str(income, "FINANCE_EXPENSE"),
        "INCOME_TAX": _field_str(income, "INCOME_TAX"),
        "OPERATE_PROFIT": _field_str(income, "OPERATE_PROFIT"),
        "report_source": "AKShare",
    }


def main() -> None:
    """Compute golden values for any frozen stock from frozen AKShare data."""
    parser = argparse.ArgumentParser(
        description="Compute golden values for any frozen stock"
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. 600519.SH")
    parser.add_argument(
        "--year", type=int, required=True, help="Fiscal year, e.g. 2023"
    )
    args = parser.parse_args()

    ticker = args.ticker
    year = args.year

    golden_dir = GOLDEN_DIR / ticker / str(year)
    if not golden_dir.is_dir():
        raise SystemExit(f"No frozen data directory at {golden_dir}")

    # Look up is_financial from manifest.yaml
    is_financial = lookup_is_financial(ticker)

    # Load frozen data
    income_records = load_frozen_records(golden_dir / "raw_akshare_income.json")
    balance_records = load_frozen_records(golden_dir / "raw_akshare_balance.json")
    cashflow_records = load_frozen_records(golden_dir / "raw_akshare_cashflow.json")

    # Extract current-year and previous-year records
    prev_year = year - 1
    income_cur = find_record_for_period(income_records, year)
    income_prev = find_record_for_period(income_records, prev_year)
    balance_cur = find_record_for_period(balance_records, year)
    balance_prev = find_record_for_period(balance_records, prev_year)
    cashflow_cur = find_record_for_period(cashflow_records, year)
    cashflow_prev = find_record_for_period(cashflow_records, prev_year)

    assert income_cur is not None, f"No {year} income record found for {ticker}"
    assert balance_cur is not None, f"No {year} balance record found for {ticker}"
    assert cashflow_cur is not None, f"No {year} cashflow record found for {ticker}"

    has_previous = all(
        v is not None for v in (income_prev, balance_prev, cashflow_prev)
    )

    # Build standardized reports
    report_cur = build_standardized_report(
        income_cur, balance_cur, cashflow_cur, ticker, year
    )

    report_prev = None
    if has_previous and income_prev and balance_prev and cashflow_prev:
        report_prev = build_standardized_report(
            income_prev, balance_prev, cashflow_prev, ticker, prev_year
        )

    # Initialize result containers
    mscore_result: dict[str, Any] = {}
    m_score_result: dict[str, Any] = {"m_score": None}
    f_score_result: dict[str, Any] = {"f_score": None}
    存贷双高_result: dict[str, Any] = {
        "存贷双高": False,
        "cash_amount": "0",
        "debt_amount": "0",
        "cash_growth_rate": 0.0,
        "debt_growth_rate": 0.0,
    }
    goodwill_result: dict[str, Any] = {"ratio": 0.0, "excessive": False}
    divergence_result: dict[str, Any] = {
        "divergence": False,
        "profit_growth": 0.0,
        "ocf_growth": 0.0,
    }

    if report_prev is not None:
        # ===== Compute M-Score indices =====
        mscore_result = calculate_mscore_indices(
            report_cur, report_prev, source_name="AKShare"
        )

        # ===== Compute M-Score composite =====
        enriched_current = {
            **report_cur,
            "days_sales_receivables_index": mscore_result["dsri"],
            "gross_margin_index": mscore_result["gmi"],
            "asset_quality_index": mscore_result["aqi"],
            "sales_growth_index": mscore_result["sgi"],
            "depreciation_index": mscore_result["depi"],
            "sga_expense_index": mscore_result["sgai"],
            "leverage_index": mscore_result["lvgi"],
            "total_accruals_to_assets": mscore_result["tata"],
        }
        m_score_result = calculate_beneish_m_score(enriched_current, report_prev)

        # ===== Compute F-Score =====
        f_score_result = calculate_piotroski_f_score(report_cur, report_prev)

        # ===== Detect 存贷双高 =====
        存贷双高_result = detect_存贷双高(report_cur, report_prev)

        # ===== Detect Profit-Cash Divergence =====
        divergence_result = detect_profit_cash_divergence(
            Decimal(report_cur.get("net_income", "0")),
            Decimal(report_prev.get("net_income", "0")),
            Decimal(report_cur.get("operating_cash_flow", "0")),
            Decimal(report_prev.get("operating_cash_flow", "0")),
        )

    # ===== Compute Goodwill Ratio (current-year only) =====
    gw_raw = report_cur.get("goodwill", "0")
    eq_raw = report_cur.get("equity_total", "1")
    # Handle None and NaN values
    if gw_raw is None or str(gw_raw) == "None" or str(gw_raw) == "nan":
        gw_raw = "0"
    if eq_raw is None or str(eq_raw) == "None" or str(eq_raw) == "nan":
        eq_raw = "1"
    goodwill_val = Decimal(str(gw_raw))
    equity_val = Decimal(str(eq_raw))
    goodwill_result = calculate_goodwill_ratio(goodwill_val, equity_val)

    # ===== Compute NOPAT, Invested Capital, ROIC =====
    profit_data = {
        "TOTAL_PROFIT": report_cur["TOTAL_PROFIT"],
        "FINANCE_EXPENSE": report_cur["FINANCE_EXPENSE"],
        "INCOME_TAX": report_cur["INCOME_TAX"],
        "OPERATE_PROFIT": report_cur["OPERATE_PROFIT"],
    }
    nopat_value, nopat_audit = calculate_nopat(profit_data, is_financial=is_financial)

    balance_sheet_data = {
        "TOTAL_PARENT_EQUITY": report_cur["TOTAL_PARENT_EQUITY"],
        "SHORT_LOAN": report_cur["SHORT_LOAN"],
        "LONG_LOAN": report_cur["LONG_LOAN"],
        "BOND_PAYABLE": report_cur["BOND_PAYABLE"],
        "TREASURY_SHARES": report_cur["TREASURY_SHARES"],
    }
    invested_capital_value, negative_ic = calculate_invested_capital(balance_sheet_data)
    roic_value = calculate_roic(nopat_value, invested_capital_value, negative_ic)

    # ===== Print all computed values =====
    print("=" * 60)
    print(f"COMPUTED GOLDEN VALUES FOR {ticker} (FY{year})")
    print(f"is_financial={is_financial}")
    print("=" * 60)

    if mscore_result:
        print("\n--- M-Score Indices ---")
        for key in ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]:
            print(f"  {key}: {mscore_result[key]}")

    if m_score_result["m_score"] is not None:
        print("\n--- M-Score Composite ---")
        print(f"  m_score: {m_score_result['m_score']}")

    if f_score_result["f_score"] is not None:
        print("\n--- F-Score ---")
        print(f"  f_score: {f_score_result['f_score']}")

    if report_prev is not None:
        print("\n--- 存贷双高 ---")
        print(f"  存贷双高: {存贷双高_result['存贷双高']}")
        print(f"  cash_amount: {存贷双高_result['cash_amount']}")
        print(f"  debt_amount: {存贷双高_result['debt_amount']}")

    print("\n--- Goodwill Ratio ---")
    print(f"  ratio: {goodwill_result['ratio']}")
    print(f"  excessive: {goodwill_result['excessive']}")

    if report_prev is not None:
        print("\n--- Profit-Cash Divergence ---")
        print(f"  divergence: {divergence_result['divergence']}")
        print(f"  profit_growth: {divergence_result['profit_growth']}")
        print(f"  ocf_growth: {divergence_result['ocf_growth']}")

    print("\n--- ROIC Components ---")
    print(f"  nopat: {nopat_value}")
    print(f"  nopat_audit: {nopat_audit}")
    print(f"  invested_capital: {invested_capital_value}")
    print(f"  negative_ic: {negative_ic}")
    print(f"  roic: {roic_value}")

    # ===== Build provenance data =====
    raw_data: dict[str, dict[str, Any]] = {
        "income_cur": {
            k: income_cur.get(k)
            for k in [
                "TOTAL_OPERATE_INCOME",
                "OPERATE_INCOME",
                "NETPROFIT",
                "OPERATE_COST",
                "TOTAL_OPERATE_COST",
                "FINANCE_EXPENSE",
                "INCOME_TAX",
                "OPERATE_PROFIT",
                "TOTAL_PROFIT",
            ]
        },
        "balance_cur": {
            k: balance_cur.get(k)
            for k in [
                "TOTAL_ASSETS",
                "TOTAL_LIABILITIES",
                "TOTAL_EQUITY",
                "TOTAL_CURRENT_ASSETS",
                "ACCOUNTS_RECE",
                "FIXED_ASSET",
                "GOODWILL",
                "MONETARYFUNDS",
                "TOTAL_PARENT_EQUITY",
                "SHORT_LOAN",
                "LONG_LOAN",
                "BOND_PAYABLE",
                "TREASURY_SHARES",
            ]
        },
        "cashflow_cur": {"NETCASH_OPERATE": cashflow_cur.get("NETCASH_OPERATE")},
    }

    if has_previous and income_prev and balance_prev and cashflow_prev:
        raw_data["income_prev"] = {
            k: income_prev.get(k)
            for k in [
                "TOTAL_OPERATE_INCOME",
                "OPERATE_INCOME",
                "NETPROFIT",
                "OPERATE_COST",
                "TOTAL_OPERATE_COST",
                "FINANCE_EXPENSE",
                "INCOME_TAX",
                "OPERATE_PROFIT",
                "TOTAL_PROFIT",
            ]
        }
        raw_data["balance_prev"] = {
            k: balance_prev.get(k)
            for k in [
                "TOTAL_ASSETS",
                "TOTAL_LIABILITIES",
                "TOTAL_CURRENT_ASSETS",
                "ACCOUNTS_RECE",
                "FIXED_ASSET",
                "MONETARYFUNDS",
                "TOTAL_PARENT_EQUITY",
                "SHORT_LOAN",
                "LONG_LOAN",
            ]
        }
        raw_data["cashflow_prev"] = {
            "NETCASH_OPERATE": cashflow_prev.get("NETCASH_OPERATE")
        }

    # ===== Write expected_metrics.yaml =====
    metrics_dict: dict[str, Any] = {
        "ticker": ticker,
        "fiscal_year": year,
        "source": "frozen_akshare_computed",
        "verified_date": None,
        "verified_by": None,
        "metrics": {
            # Risk category -- M-Score indices
            "dsri": {
                "value": mscore_result.get("dsri") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "gmi": {
                "value": mscore_result.get("gmi") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "aqi": {
                "value": mscore_result.get("aqi") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "sgi": {
                "value": mscore_result.get("sgi") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "depi": {
                "value": mscore_result.get("depi") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "sgai": {
                "value": mscore_result.get("sgai") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "lvgi": {
                "value": mscore_result.get("lvgi") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "tata": {
                "value": mscore_result.get("tata") if mscore_result else None,
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "m_score": {
                "value": m_score_result["m_score"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "f_score": {
                "value": f_score_result["f_score"],
                "tolerance": {"absolute": 0},
                "source_page": None,
            },
            "detect_存贷双高": {
                "value": (bool(存贷双高_result["存贷双高"]) if report_prev else None),
                "tolerance": {"absolute": 0.01},
                "source_page": None,
            },
            "goodwill_ratio": {
                "value": goodwill_result["ratio"],
                "tolerance": {"relative": 0.01},
                "source_page": None,
            },
            "profit_cash_divergence": {
                "value": (
                    bool(divergence_result["divergence"]) if report_prev else None
                ),
                "tolerance": {"absolute": 0.01},
                "source_page": None,
            },
            # ROIC category
            "nopat": {
                "value": nopat_value,
                "tolerance": {"relative": 0.02},
                "source_page": None,
            },
            "invested_capital": {
                "value": invested_capital_value,
                "tolerance": {"relative": 0.02},
                "source_page": None,
            },
            "roic": {
                "value": roic_value,
                "tolerance": {"relative": 0.01},
                "source_page": None,
            },
            "roic_wacc_spread": {
                "value": None,
                "tolerance": {"absolute": 0.001},
                "source_page": None,
                "skip_reason": "Depends on WACC which requires market data (beta, risk-free rate, ERP)",
            },
            # Valuation category (requires market data)
            "wacc": {
                "value": None,
                "tolerance": {"relative": 0.01},
                "source_page": None,
                "skip_reason": "Requires market data (beta, risk-free rate, equity risk premium)",
            },
            "present_value": {
                "value": None,
                "tolerance": {"relative": 0.02},
                "source_page": None,
                "skip_reason": "Requires multi-year FCF projections and WACC",
            },
            "terminal_value": {
                "value": None,
                "tolerance": {"relative": 0.02},
                "source_page": None,
                "skip_reason": "Requires multi-year growth assumptions and WACC",
            },
            "margin_of_safety": {
                "value": None,
                "tolerance": {"relative": 0.01},
                "source_page": None,
                "skip_reason": "Requires current market price and intrinsic value calculation",
            },
            # Yield category
            "net_dividend_yield": {
                "value": None,
                "tolerance": {"relative": 0.01},
                "source_page": None,
                "skip_reason": "Requires dividend per share and current stock price",
            },
            "yield_gap": {
                "value": None,
                "tolerance": {"relative": 0.01},
                "source_page": None,
                "skip_reason": "Requires net_dividend_yield and risk-free rates",
            },
            # CapEx category
            "buyback_yield": {
                "value": None,
                "tolerance": {"relative": 0.01},
                "source_page": None,
                "skip_reason": "Requires share buyback data and market capitalization",
            },
            "capital_allocation_score": {
                "value": None,
                "tolerance": {"absolute": 0.5},
                "source_page": None,
                "skip_reason": "Composite metric requiring buyback, dividend, and expansion grades",
            },
            # Policy category
            "resonance_score": {
                "value": None,
                "tolerance": {"absolute": 1.0},
                "source_page": None,
                "skip_reason": "Requires LLM semantic matching against policy documents",
            },
            "dcf_adjustment": {
                "value": None,
                "tolerance": {"absolute": 0.001},
                "source_page": None,
                "skip_reason": "Requires policy resonance engine and terminal growth rate",
            },
            # Alpha category
            "alpha_score": {
                "value": None,
                "tolerance": {"absolute": 0.1},
                "source_page": None,
                "skip_reason": "Composite metric requiring ROIC-WACC spread, CapEx score, policy score, and moat trend",
            },
        },
    }

    metrics_path = golden_dir / "expected_metrics.yaml"
    metrics_path.write_text(
        yaml.dump(
            metrics_dict,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote: {metrics_path}")

    # ===== Write provenance.md =====
    frozen_date = json.loads((golden_dir / "raw_akshare_income.json").read_text())[
        "_metadata"
    ]["frozen_date"]

    nopat_branch = (
        "is_financial=True (OPERATE_PROFIT branch)"
        if is_financial
        else "is_financial=False (TOTAL_PROFIT + FINANCE_EXPENSE branch)"
    )

    prev_section = ""
    if "income_prev" in raw_data:
        prev_section = f"""
### Previous Year (FY{prev_year}) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | {raw_data["income_prev"].get("TOTAL_OPERATE_INCOME")} |
| Net Income | {raw_data["income_prev"].get("NETPROFIT")} |
| Total Assets | {raw_data["balance_prev"].get("TOTAL_ASSETS")} |
| Total Current Assets | {raw_data["balance_prev"].get("TOTAL_CURRENT_ASSETS")} |
| PPE | {raw_data["balance_prev"].get("FIXED_ASSET")} |
| SGA Expense | {raw_data["income_prev"].get("TOTAL_OPERATE_COST")} |
| Total Liabilities | {raw_data["balance_prev"].get("TOTAL_LIABILITIES")} |
| Accounts Receivable | {raw_data["balance_prev"].get("ACCOUNTS_RECE")} |
| Operating Cash Flow | {raw_data["cashflow_prev"].get("NETCASH_OPERATE")} |
"""

    mscore_table = ""
    if mscore_result:
        mscore_table = f"""
| DSRI | {mscore_result["dsri"]} | calculate_mscore_indices |
| GMI | {mscore_result["gmi"]} | calculate_mscore_indices |
| AQI | {mscore_result["aqi"]} | calculate_mscore_indices |
| SGI | {mscore_result["sgi"]} | calculate_mscore_indices |
| DEPI | {mscore_result["depi"]} | calculate_mscore_indices |
| SGAI | {mscore_result["sgai"]} | calculate_mscore_indices |
| LVGI | {mscore_result["lvgi"]} | calculate_mscore_indices |
| TATA | {mscore_result["tata"]} | calculate_mscore_indices |
"""
    if m_score_result["m_score"] is not None:
        mscore_table += (
            f"| M-Score | {m_score_result['m_score']} | calculate_beneish_m_score |\n"
        )
    if f_score_result["f_score"] is not None:
        mscore_table += (
            f"| F-Score | {f_score_result['f_score']} | calculate_piotroski_f_score |\n"
        )

    provenance = f"""# Provenance: {ticker} FY{year}

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: {frozen_date}
- **Period**: FY{year} ({year}1231) + FY{prev_year} ({prev_year}1231) for year-over-year indices
- **is_financial**: {is_financial}

## Computation Method
All golden values computed from frozen AKShare data using production calculate_* functions:
- M-Score 8 sub-indices: `calculate_mscore_indices(current_{year}, previous_{prev_year}, "AKShare")`
- M-Score composite: `calculate_beneish_m_score(current_financials, previous_financials)`
- F-Score: `calculate_piotroski_f_score(report_{year}, previous_report_{prev_year})`
- 存贷双高: `detect_存贷双高(report_{year}, report_{prev_year})`
- Goodwill ratio: `calculate_goodwill_ratio(goodwill, equity)`
- Profit-cash divergence: `detect_profit_cash_divergence(profit_{year}, profit_{prev_year}, ocf_{year}, ocf_{prev_year})`
- NOPAT: `calculate_nopat(profit_data, {nopat_branch})`
- Invested Capital: `calculate_invested_capital(balance_sheet_data)`
- ROIC: `calculate_roic(nopat, invested_capital, negative_ic)`

## Raw Financial Data (from frozen AKShare)

### Income Statement (FY{year})
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Revenue | TOTAL_OPERATE_INCOME | {raw_data["income_cur"].get("TOTAL_OPERATE_INCOME")} |
| Net Income | NETPROFIT | {raw_data["income_cur"].get("NETPROFIT")} |
| Cost of Goods | OPERATE_COST | {raw_data["income_cur"].get("OPERATE_COST")} |
| SGA Expense | TOTAL_OPERATE_COST | {raw_data["income_cur"].get("TOTAL_OPERATE_COST")} |
| Finance Expense | FINANCE_EXPENSE | {raw_data["income_cur"].get("FINANCE_EXPENSE")} |
| Income Tax | INCOME_TAX | {raw_data["income_cur"].get("INCOME_TAX")} |
| Operating Profit | OPERATE_PROFIT | {raw_data["income_cur"].get("OPERATE_PROFIT")} |
| Total Profit | TOTAL_PROFIT | {raw_data["income_cur"].get("TOTAL_PROFIT")} |

### Balance Sheet (FY{year})
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | {raw_data["balance_cur"].get("TOTAL_ASSETS")} |
| Total Equity | TOTAL_EQUITY | {raw_data["balance_cur"].get("TOTAL_EQUITY")} |
| Total Liabilities | TOTAL_LIABILITIES | {raw_data["balance_cur"].get("TOTAL_LIABILITIES")} |
| Current Assets | TOTAL_CURRENT_ASSETS | {raw_data["balance_cur"].get("TOTAL_CURRENT_ASSETS")} |
| Accounts Receivable | ACCOUNTS_RECE | {raw_data["balance_cur"].get("ACCOUNTS_RECE")} |
| PPE | FIXED_ASSET | {raw_data["balance_cur"].get("FIXED_ASSET")} |
| Goodwill | GOODWILL | {raw_data["balance_cur"].get("GOODWILL")} |
| Cash | MONETARYFUNDS | {raw_data["balance_cur"].get("MONETARYFUNDS")} |
| Parent Equity | TOTAL_PARENT_EQUITY | {raw_data["balance_cur"].get("TOTAL_PARENT_EQUITY")} |
| Short Loan | SHORT_LOAN | {raw_data["balance_cur"].get("SHORT_LOAN")} |
| Long Loan | LONG_LOAN | {raw_data["balance_cur"].get("LONG_LOAN")} |
| Bond Payable | BOND_PAYABLE | {raw_data["balance_cur"].get("BOND_PAYABLE")} |
| Treasury Shares | TREASURY_SHARES | {raw_data["balance_cur"].get("TREASURY_SHARES")} |

### Cash Flow Statement (FY{year})
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | {raw_data["cashflow_cur"].get("NETCASH_OPERATE")} |
{prev_section}
## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|
{mscore_table}| 存贷双高 | {bool(存贷双高_result["存贷双高"]) if report_prev else "N/A"} | detect_存贷双高 |
| Goodwill Ratio | {goodwill_result["ratio"]} | calculate_goodwill_ratio |
| Profit-Cash Divergence | {bool(divergence_result["divergence"]) if report_prev else "N/A"} | detect_profit_cash_divergence |
| NOPAT | {nopat_value} | calculate_nopat ({nopat_branch}) |
| Invested Capital | {invested_capital_value} | calculate_invested_capital |
| ROIC | {roic_value} | calculate_roic |

## Skipped Metrics
| Metric | Reason |
|--------|--------|
| WACC | Requires market data (beta, risk-free rate, ERP) |
| Present Value | Requires multi-year FCF projections |
| Terminal Value | Requires multi-year growth assumptions |
| Margin of Safety | Requires current market price |
| Net Dividend Yield | Requires dividend per share and stock price |
| Yield Gap | Requires net_dividend_yield and risk-free rates |
| Buyback Yield | Requires share buyback data |
| Capital Allocation Score | Composite of above skipped metrics |
| Resonance Score | Requires LLM semantic matching |
| DCF Adjustment | Requires policy resonance engine |
| Alpha Score | Composite of LLM-dependent metrics |
| ROIC-WACC Spread | Depends on WACC (skipped) |

## Verifier
- **Date**: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
- **Method**: Computed from frozen AKShare data using calculate_* functions
- **Confidence**: Deterministic -- values are exact outputs of production code
- **is_financial**: {is_financial}
- **Note**: Values should be cross-referenced with CNINFO annual report PDF for L3 verification
"""

    provenance_path = golden_dir / "provenance.md"
    provenance_path.write_text(provenance, encoding="utf-8")
    print(f"Wrote: {provenance_path}")


if __name__ == "__main__":
    main()
