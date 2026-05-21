"""Compute golden values for 600519.SH from frozen AKShare data.

This script loads the frozen AKShare JSON for 600519.SH, transforms it into
the same standardized dict format used by data_service.py, then calls the
production calculate_* functions to compute exact golden values.

The output is written to expected_metrics.yaml and provenance.md.
"""

from __future__ import annotations

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
    """Compute golden values for 600519.SH from frozen AKShare data."""
    golden_dir = GOLDEN_DIR / "600519.SH" / "2023"

    # Load frozen data
    income_records = load_frozen_records(golden_dir / "raw_akshare_income.json")
    balance_records = load_frozen_records(golden_dir / "raw_akshare_balance.json")
    cashflow_records = load_frozen_records(golden_dir / "raw_akshare_cashflow.json")

    # Extract 2023 and 2022 records
    income_2023 = find_record_for_period(income_records, 2023)
    income_2022 = find_record_for_period(income_records, 2022)
    balance_2023 = find_record_for_period(balance_records, 2023)
    balance_2022 = find_record_for_period(balance_records, 2022)
    cashflow_2023 = find_record_for_period(cashflow_records, 2023)
    cashflow_2022 = find_record_for_period(cashflow_records, 2022)

    assert income_2023 is not None, "No 2023 income record found"
    assert income_2022 is not None, "No 2022 income record found"
    assert balance_2023 is not None, "No 2023 balance record found"
    assert balance_2022 is not None, "No 2022 balance record found"
    assert cashflow_2023 is not None, "No 2023 cashflow record found"
    assert cashflow_2022 is not None, "No 2022 cashflow record found"

    # Build standardized reports
    report_2023 = build_standardized_report(
        income_2023, balance_2023, cashflow_2023, "600519.SH", 2023
    )
    report_2022 = build_standardized_report(
        income_2022, balance_2022, cashflow_2022, "600519.SH", 2022
    )

    # ===== Compute M-Score indices =====
    mscore_result = calculate_mscore_indices(
        report_2023, report_2022, source_name="AKShare"
    )

    # ===== Compute M-Score composite =====
    # Inject calculated indices into enriched current report
    enriched_current = {
        **report_2023,
        "days_sales_receivables_index": mscore_result["dsri"],
        "gross_margin_index": mscore_result["gmi"],
        "asset_quality_index": mscore_result["aqi"],
        "sales_growth_index": mscore_result["sgi"],
        "depreciation_index": mscore_result["depi"],
        "sga_expense_index": mscore_result["sgai"],
        "leverage_index": mscore_result["lvgi"],
        "total_accruals_to_assets": mscore_result["tata"],
    }
    m_score_result = calculate_beneish_m_score(enriched_current, report_2022)

    # ===== Compute F-Score =====
    f_score_result = calculate_piotroski_f_score(report_2023, report_2022)

    # ===== Detect 存贷双高 =====
    存贷双高_result = detect_存贷双高(report_2023, report_2022)

    # ===== Compute Goodwill Ratio =====
    goodwill_val = Decimal(report_2023.get("goodwill", "0"))
    equity_val = Decimal(report_2023.get("equity_total", "1"))
    goodwill_result = calculate_goodwill_ratio(goodwill_val, equity_val)

    # ===== Detect Profit-Cash Divergence =====
    divergence_result = detect_profit_cash_divergence(
        Decimal(report_2023.get("net_income", "0")),
        Decimal(report_2022.get("net_income", "0")),
        Decimal(report_2023.get("operating_cash_flow", "0")),
        Decimal(report_2022.get("operating_cash_flow", "0")),
    )

    # ===== Compute NOPAT, Invested Capital, ROIC =====
    profit_data = {
        "TOTAL_PROFIT": report_2023["TOTAL_PROFIT"],
        "FINANCE_EXPENSE": report_2023["FINANCE_EXPENSE"],
        "INCOME_TAX": report_2023["INCOME_TAX"],
        "OPERATE_PROFIT": report_2023["OPERATE_PROFIT"],
    }
    nopat_value, nopat_audit = calculate_nopat(profit_data, is_financial=False)

    balance_sheet_data = {
        "TOTAL_PARENT_EQUITY": report_2023["TOTAL_PARENT_EQUITY"],
        "SHORT_LOAN": report_2023["SHORT_LOAN"],
        "LONG_LOAN": report_2023["LONG_LOAN"],
        "BOND_PAYABLE": report_2023["BOND_PAYABLE"],
        "TREASURY_SHARES": report_2023["TREASURY_SHARES"],
    }
    invested_capital_value, negative_ic = calculate_invested_capital(balance_sheet_data)
    roic_value = calculate_roic(nopat_value, invested_capital_value, negative_ic)

    # ===== Print all computed values =====
    print("=" * 60)
    print("COMPUTED GOLDEN VALUES FOR 600519.SH (FY2023)")
    print("=" * 60)

    print("\n--- M-Score Indices ---")
    for key in ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]:
        print(f"  {key}: {mscore_result[key]}")

    print("\n--- M-Score Composite ---")
    print(f"  m_score: {m_score_result['m_score']}")

    print("\n--- F-Score ---")
    print(f"  f_score: {f_score_result['f_score']}")

    print("\n--- 存贷双高 ---")
    print(f"  存贷双高: {存贷双高_result['存贷双高']}")
    print(f"  cash_amount: {存贷双高_result['cash_amount']}")
    print(f"  debt_amount: {存贷双高_result['debt_amount']}")
    print(f"  cash_growth_rate: {存贷双高_result['cash_growth_rate']}")
    print(f"  debt_growth_rate: {存贷双高_result['debt_growth_rate']}")

    print("\n--- Goodwill Ratio ---")
    print(f"  ratio: {goodwill_result['ratio']}")
    print(f"  excessive: {goodwill_result['excessive']}")

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
    raw_data = {
        "income_2023": {
            k: income_2023.get(k)
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
        "balance_2023": {
            k: balance_2023.get(k)
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
        "cashflow_2023": {"NETCASH_OPERATE": cashflow_2023.get("NETCASH_OPERATE")},
        "income_2022": {
            k: income_2022.get(k)
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
        "balance_2022": {
            k: balance_2022.get(k)
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
        },
        "cashflow_2022": {"NETCASH_OPERATE": cashflow_2022.get("NETCASH_OPERATE")},
    }

    # ===== Write expected_metrics.yaml =====
    metrics = {
        "ticker": "600519.SH",
        "fiscal_year": 2023,
        "source": "frozen_akshare_computed",
        "verified_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "verified_by": "compute_golden_values.py (deterministic)",
        "metrics": {
            # Risk category
            "dsri": {
                "value": mscore_result["dsri"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "gmi": {
                "value": mscore_result["gmi"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "aqi": {
                "value": mscore_result["aqi"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "sgi": {
                "value": mscore_result["sgi"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "depi": {
                "value": mscore_result["depi"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "sgai": {
                "value": mscore_result["sgai"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "lvgi": {
                "value": mscore_result["lvgi"],
                "tolerance": {"absolute": 0.05},
                "source_page": None,
            },
            "tata": {
                "value": mscore_result["tata"],
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
                "value": bool(存贷双高_result["存贷双高"]),
                "tolerance": {"absolute": 0.01},
                "source_page": None,
            },
            "goodwill_ratio": {
                "value": goodwill_result["ratio"],
                "tolerance": {"relative": 0.01},
                "source_page": None,
            },
            "profit_cash_divergence": {
                "value": bool(divergence_result["divergence"]),
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
            metrics, allow_unicode=True, default_flow_style=False, sort_keys=False
        ),
        encoding="utf-8",
    )
    print(f"\nWrote: {metrics_path}")

    # ===== Write provenance.md =====
    frozen_date = json.loads((golden_dir / "raw_akshare_income.json").read_text())[
        "_metadata"
    ]["frozen_date"]

    provenance = f"""# Provenance: 600519.SH (Kweichow Moutai) FY2023

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: {frozen_date}
- **Period**: FY2023 (20231231) + FY2022 (20221231) for year-over-year indices

## Computation Method
All golden values computed from frozen AKShare data using production calculate_* functions:
- M-Score 8 sub-indices: `calculate_mscore_indices(current_2023, previous_2022, "AKShare")`
- M-Score composite: `calculate_beneish_m_score(current_financials, previous_financials)`
- F-Score: `calculate_piotroski_f_score(report_2023, previous_report_2022)`
- 存贷双高: `detect_存贷双高(report_2023, report_2022)`
- Goodwill ratio: `calculate_goodwill_ratio(goodwill, equity)`
- Profit-cash divergence: `detect_profit_cash_divergence(profit_2023, profit_2022, ocf_2023, ocf_2022)`
- NOPAT: `calculate_nopat(profit_data, is_financial=False)`
- Invested Capital: `calculate_invested_capital(balance_sheet_data)`
- ROIC: `calculate_roic(nopat, invested_capital, negative_ic)`

## Raw Financial Data (from frozen AKShare)

### Income Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Revenue | TOTAL_OPERATE_INCOME | {raw_data["income_2023"].get("TOTAL_OPERATE_INCOME")} |
| Net Income | NETPROFIT | {raw_data["income_2023"].get("NETPROFIT")} |
| Cost of Goods | OPERATE_COST | {raw_data["income_2023"].get("OPERATE_COST")} |
| SGA Expense | TOTAL_OPERATE_COST | {raw_data["income_2023"].get("TOTAL_OPERATE_COST")} |
| Finance Expense | FINANCE_EXPENSE | {raw_data["income_2023"].get("FINANCE_EXPENSE")} |
| Income Tax | INCOME_TAX | {raw_data["income_2023"].get("INCOME_TAX")} |
| Operating Profit | OPERATE_PROFIT | {raw_data["income_2023"].get("OPERATE_PROFIT")} |
| Total Profit | TOTAL_PROFIT | {raw_data["income_2023"].get("TOTAL_PROFIT")} |

### Balance Sheet (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | {raw_data["balance_2023"].get("TOTAL_ASSETS")} |
| Total Equity | TOTAL_EQUITY | {raw_data["balance_2023"].get("TOTAL_EQUITY")} |
| Total Liabilities | TOTAL_LIABILITIES | {raw_data["balance_2023"].get("TOTAL_LIABILITIES")} |
| Current Assets | TOTAL_CURRENT_ASSETS | {raw_data["balance_2023"].get("TOTAL_CURRENT_ASSETS")} |
| Accounts Receivable | ACCOUNTS_RECE | {raw_data["balance_2023"].get("ACCOUNTS_RECE")} |
| PPE | FIXED_ASSET | {raw_data["balance_2023"].get("FIXED_ASSET")} |
| Goodwill | GOODWILL | {raw_data["balance_2023"].get("GOODWILL")} |
| Cash | MONETARYFUNDS | {raw_data["balance_2023"].get("MONETARYFUNDS")} |
| Parent Equity | TOTAL_PARENT_EQUITY | {raw_data["balance_2023"].get("TOTAL_PARENT_EQUITY")} |
| Short Loan | SHORT_LOAN | {raw_data["balance_2023"].get("SHORT_LOAN")} |
| Long Loan | LONG_LOAN | {raw_data["balance_2023"].get("LONG_LOAN")} |
| Bond Payable | BOND_PAYABLE | {raw_data["balance_2023"].get("BOND_PAYABLE")} |
| Treasury Shares | TREASURY_SHARES | {raw_data["balance_2023"].get("TREASURY_SHARES")} |

### Cash Flow Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | {raw_data["cashflow_2023"].get("NETCASH_OPERATE")} |

### Previous Year (FY2022) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | {raw_data["income_2022"].get("TOTAL_OPERATE_INCOME")} |
| Net Income | {raw_data["income_2022"].get("NETPROFIT")} |
| Total Assets | {raw_data["balance_2022"].get("TOTAL_ASSETS")} |
| Total Current Assets | {raw_data["balance_2022"].get("TOTAL_CURRENT_ASSETS")} |
| PPE | {raw_data["balance_2022"].get("FIXED_ASSET")} |
| SGA Expense | {raw_data["income_2022"].get("TOTAL_OPERATE_COST")} |
| Total Liabilities | {raw_data["balance_2022"].get("TOTAL_LIABILITIES")} |
| Accounts Receivable | {raw_data["balance_2022"].get("ACCOUNTS_RECE")} |
| Operating Cash Flow | {raw_data["cashflow_2022"].get("NETCASH_OPERATE")} |

## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|
| DSRI | {mscore_result["dsri"]} | calculate_mscore_indices |
| GMI | {mscore_result["gmi"]} | calculate_mscore_indices |
| AQI | {mscore_result["aqi"]} | calculate_mscore_indices |
| SGI | {mscore_result["sgi"]} | calculate_mscore_indices |
| DEPI | {mscore_result["depi"]} | calculate_mscore_indices |
| SGAI | {mscore_result["sgai"]} | calculate_mscore_indices |
| LVGI | {mscore_result["lvgi"]} | calculate_mscore_indices |
| TATA | {mscore_result["tata"]} | calculate_mscore_indices |
| M-Score | {m_score_result["m_score"]} | calculate_beneish_m_score |
| F-Score | {f_score_result["f_score"]} | calculate_piotroski_f_score |
| 存贷双高 | {bool(存贷双高_result["存贷双高"])} | detect_存贷双高 |
| Goodwill Ratio | {goodwill_result["ratio"]} | calculate_goodwill_ratio |
| Profit-Cash Divergence | {bool(divergence_result["divergence"])} | detect_profit_cash_divergence |
| NOPAT | {nopat_value} | calculate_nopat |
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
- **Note**: Values should be cross-referenced with CNINFO annual report PDF for L3 verification
"""

    provenance_path = golden_dir / "provenance.md"
    provenance_path.write_text(provenance, encoding="utf-8")
    print(f"Wrote: {provenance_path}")


if __name__ == "__main__":
    main()
