# Technology Stack

**Project:** StockValueFinder v1.2 Alpha Engine
**Researched:** 2026-05-03
**Scope:** Stack additions for ROIC-WACC spread, Capital Allocation scorecard, Policy Resonance Engine, Composite Alpha score

## Recommended Stack Changes

### New Dependencies

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| scipy | >=1.15.0 | Linear regression for 3-year ROIC-WACC trend (moat detection) | `scipy.stats.linregress` provides slope + p-value for trend significance. numpy alone requires manual implementation. scipy is standard for statistical analysis and has no native alternatives at this weight. Already a transitive dependency of pandas/numpy ecosystem. |
| numpy | >=2.4.0 | Array operations for multi-year financial data | Already installed as transitive dependency (v2.4.2 confirmed). Pin explicitly in pyproject.toml for version stability since ROIC calculations depend on it. |

### No New Infrastructure Required

All new features integrate into the existing stack without additional infrastructure:

| Component | Already Exists | How It's Used for New Features |
|-----------|---------------|-------------------------------|
| Qdrant | Yes (Docker) | Policy Resonance Engine stores policy document chunks in a separate `policy_documents` collection with `report_type=policy` filter |
| Redis | Yes (Docker) | Cache ROIC/NOPAT calculations, buyback data, policy match results |
| PostgreSQL | Yes | 3 new ORM models + 1 Alembic migration for ROIC results, capital allocation scores, composite Alpha |
| DeepSeek LLM | Yes | Policy-to-DCF parameter extraction narrative; optional narrative for Alpha score explanation |
| AKShare 1.18+ | Yes | ROIC inputs from existing `stock_profit_sheet_by_report_em`, `stock_balance_sheet_by_report_em`, `stock_cash_flow_sheet_by_report_em`. Buyback data from `stock_repurchase_em` |
| bge-m3 embeddings | Yes | Policy document embedding uses same BGEEmbeddingClient |
| PyMuPDF | Yes | Policy PDF processing reuses existing PDF processor |

## Detailed Data Source Mapping

### ROIC-WACC Spread: AKShare API Mapping

ROIC = NOPAT / Invested Capital. All inputs available from existing AKShare functions. **No new API calls needed** -- the codebase already calls `get_profit_sheet`, `get_balance_sheet`, and `get_cash_flow_sheet`. The new work is extracting additional columns from the same responses.

| Metric | Formula | AKShare Source Function | Column Name(s) | Confidence |
|--------|---------|------------------------|-----------------|------------|
| EBIT | Total Profit + Finance Expense | `stock_profit_sheet_by_report_em` | `TOTAL_PROFIT` + `FINANCE_EXPENSE` | HIGH -- verified live data for 600519 |
| Tax Rate | Income Tax / Total Profit | `stock_profit_sheet_by_report_em` | `INCOME_TAX` / `TOTAL_PROFIT` | HIGH -- verified |
| NOPAT | EBIT * (1 - Tax Rate) | Derived from above | Computed field | HIGH |
| Total Equity | Shareholders' equity | `stock_balance_sheet_by_report_em` | `TOTAL_PARENT_EQUITY` | HIGH -- verified |
| Short-term Debt | Short-term borrowings | `stock_balance_sheet_by_report_em` | `SHORT_LOAN` | HIGH -- verified |
| Long-term Debt | Long-term borrowings | `stock_balance_sheet_by_report_em` | `LONG_LOAN` | HIGH -- verified |
| Bonds Payable | Bond obligations | `stock_balance_sheet_by_report_em` | `BOND_PAYABLE` | HIGH -- verified |
| Treasury Shares | Share repurchases (balance sheet) | `stock_balance_sheet_by_report_em` | `TREASURY_SHARES` | HIGH -- verified |
| Invested Capital | Total Equity + Short Loan + Long Loan + Bonds Payable - Treasury Shares | Derived | Computed field | HIGH |
| ROIC | NOPAT / Invested Capital | Derived | Computed field | HIGH |
| WACC | Already calculated in `valuation_service.py` via CAPM | `calculate_wacc()` | Existing function | HIGH -- reuse directly |

**NOPAT derivation detail:**
```
# Verified against live 600519 data:
# TOTAL_PROFIT = 37,543,249,644.02
# FINANCE_EXPENSE = -115,803,334.98 (negative = net interest income)
# EBIT = TOTAL_PROFIT + abs(FINANCE_EXPENSE) if FINANCE_EXPENSE < 0
#      (For banks/financials: EBIT = OPERATE_PROFIT directly)
# INCOME_TAX = 9,389,418,154.13
# Tax Rate = INCOME_TAX / TOTAL_PROFIT = 0.2502
# NOPAT = EBIT * (1 - Tax Rate)
```

**Important caveat:** AKShare returns `nan` for `SHORT_LOAN` and `LONG_LOAN` when the company has no short/long-term bank borrowings (e.g., Maotai). The code must handle `nan` as 0.0 for debt fields.

### Capital Allocation Scorecard: AKShare API Mapping

| Metric | AKShare Source | Column(s) | Notes |
|--------|---------------|-----------|-------|
| Buyback Yield | `stock_repurchase_em()` | `已回购金额`, `股票代码` | Market-wide dataset (5088 rows). Filter by `股票代码 == '600519'`. Compute yield = `已回购金额` / market_cap. **Takes no arguments** -- returns all stocks. |
| Dividend Stability (5-year DPU) | `stock_history_dividend_detail()` (already used) | `送股`, `派息` columns | Already integrated in `akshare_client.get_dividend_history()`. Need to extract 5 years of per-share dividend and compute coefficient of variation. |
| CapEx Surge Detection | `stock_cash_flow_sheet_by_report_em` | `CONSTRUCT_LONG_ASSET` | Verified column exists. This is the standard CapEx proxy ("cash paid for acquiring fixed assets, intangible assets and other long-term assets"). |
| Blind Expansion Alert | Derived: ROIC < WACC AND CapEx YoY growth > threshold | Above sources | Compare ROIC-WACC spread (negative) against CapEx growth rate |

**Buyback yield calculation:**
- `stock_repurchase_em()` returns ALL stocks -- filter by `股票代码` matching the 6-digit code portion of ticker
- Compute: buyback_yield = `已回购金额` / (current_price * total_shares_outstanding)
- Cache: 24h TTL (same as financial data)

### Policy Resonance Engine: Existing RAG Infrastructure

| Component | Existing Code | New Usage |
|-----------|--------------|-----------|
| PDF Upload | `documents_routes.py` upload endpoint | Reuse for policy document uploads. Add `document_type=policy` metadata. |
| PDF Processing | `rag/pdf_processor.py` | Reuse unchanged. Policy PDFs chunk identically to annual reports. |
| Embedding | `rag/embeddings.py` BGEEmbeddingClient | Reuse unchanged. bge-m3 handles policy/government Chinese text well. |
| Vector Store | `rag/vector_store.py` QdrantVectorStore | Reuse. Instantiate with `collection="policy_documents"`. Separate collection from `annual_reports`. |
| Retrieval | `rag/retriever.py` SemanticRetriever | Reuse with new collection parameter. Policy queries match against policy chunks. |
| LLM Extraction | DeepSeek via `llm_factory.py` | New prompt template: extract DCF parameter adjustments from matched policy text. |

**Why separate Qdrant collection:** Policy documents have fundamentally different metadata (no `ticker`, no `year`, no `company_name`). Mixing them into `annual_reports` collection would pollute ticker/year filters and require schema changes to ChunkMetadata. A separate `policy_documents` collection is cleaner and avoids breaking existing search.

## New Files to Create

### Services (pure functions following existing pattern)

| File | Purpose | Key Functions |
|------|---------|--------------|
| `services/roic_service.py` | ROIC-WACC spread calculation | `calculate_nopat()`, `calculate_invested_capital()`, `calculate_roic()`, `calculate_roic_wacc_spread()`, `analyze_roic_trend()` (3-year linregress) |
| `services/capital_allocation_service.py` | Capital allocation scorecard | `calculate_buyback_yield()`, `calculate_dividend_stability()`, `detect_capex_surge()`, `detect_blind_expansion()`, `calculate_capital_allocation_score()` |
| `services/policy_resonance_service.py` | Policy document RAG matching + DCF parameter adjustment | `match_policy_to_stock()`, `extract_dcf_adjustments()`, `calculate_policy_resonance_score()` |
| `services/alpha_composite_service.py` | Weighted composite Alpha score | `calculate_composite_alpha()` with fixed weights: 40% ROIC-WACC, 30% Capital Allocation, 20% Policy, 10% Moat trend |
| `services/narrative_prompts.py` | (Extend existing) | Add prompt templates for ROIC, capital allocation, policy resonance narratives |

### External Client Extensions

| File | Change | New Methods |
|------|--------|------------|
| `external/akshare_client.py` | Extend existing | `get_repurchase_data()` -- wraps `stock_repurchase_em()`, filters by stock code |
| `external/data_service.py` | Extend existing | `get_roic_inputs()` -- orchestrates profit sheet + balance sheet, returns EBIT, tax rate, equity, debt, treasury shares. `get_capex_data()` -- extracts CONSTRUCT_LONG_ASSET. `get_buyback_data()` -- wraps repurchase API. |

### Domain Models (Pydantic)

| File | Purpose | Key Models |
|------|---------|-----------|
| `models/roic.py` | ROIC analysis domain models | `ROICData` (frozen), `ROICWACCSpread`, `ROICTrend`, `ROICAnalysisRequest` |
| `models/capital_allocation.py` | Capital allocation scorecard | `BuybackData`, `DividendStability`, `CapitalAllocationScore`, `CapitalAllocationRequest` |
| `models/policy_resonance.py` | Policy resonance models | `PolicyMatch`, `DCFAdjustment`, `PolicyResonanceResult` |
| `models/alpha_composite.py` | Composite Alpha score | `AlphaComponentWeights` (frozen), `CompositeAlphaResult` |

### ORM Models (SQLAlchemy)

| File | Purpose | Key Columns |
|------|---------|------------|
| `db/models/roic.py` | Persist ROIC results | ticker, fiscal_year, nopat, invested_capital, roic, wacc, spread, spread_trend, trend_p_value, calculated_at |
| `db/models/capital_allocation.py` | Persist scorecard | ticker, fiscal_year, buyback_yield, dividend_cv, capex_yoy, blind_expansion_flag, score, calculated_at |
| `db/models/alpha_composite.py` | Persist composite Alpha | ticker, roic_wacc_score, capital_alloc_score, policy_score, moat_score, composite_alpha, calculated_at |

### Repositories

| File | Purpose |
|------|---------|
| `repositories/roic_repo.py` | CRUD for ROIC results with `get_by_ticker_and_year`, `upsert_by_report_id` pattern |
| `repositories/capital_allocation_repo.py` | CRUD for capital allocation scores |
| `repositories/alpha_repo.py` | CRUD for composite Alpha scores |

### API Routes

| File | Endpoints |
|------|-----------|
| `api/alpha_routes.py` | `POST /api/v1/alpha/roic` -- ROIC-WACC analysis; `POST /api/v1/alpha/capital-allocation` -- capital allocation scorecard; `POST /api/v1/alpha/composite` -- full composite Alpha; `POST /api/v1/alpha/policy/upload` -- policy document upload; `POST /api/v1/alpha/policy/match` -- match policy to stock |

### Configuration

| File | Change |
|------|--------|
| `config.py` | Add `AlphaConfig` (frozen dataclass): ROIC_WACC_WEIGHT=0.40, CAPITAL_ALLOC_WEIGHT=0.30, POLICY_WEIGHT=0.20, MOAT_WEIGHT=0.10, MOAT_TREND_YEARS=3, BLIND_EXPANSION_CAPEX_THRESHOLD=0.30, DIVIDEND_STABILITY_YEARS=5. Add `POLICY_COLLECTION` to RAGConfig. |

### Alembic Migration

| File | Change |
|------|--------|
| `alembic/versions/011_alpha_engine_tables.py` | Create `roic_results`, `capital_allocation_scores`, `composite_alpha_results` tables. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Trend detection | scipy.stats.linregress | numpy polyfit | linregress provides p-value for statistical significance. polyfit only gives coefficients. For 3-year moat detection, p-value is essential to distinguish real trends from noise. |
| Trend detection | scipy.stats.linregress | statsmodels OLS | Overkill for simple 3-point regression. statsmodels is 10x heavier and not installed. |
| Policy RAG storage | Separate Qdrant collection | Same collection with metadata filter | Policy docs lack ticker/year fields. Mixing pollutes existing filters. Separate collection keeps schemas clean and avoids breaking changes. |
| Buyback data | AKShare `stock_repurchase_em()` | Manual web scraping | AKShare provides structured data (5088 stocks, includes amounts and progress). Scraping is brittle and violates rate limits. |
| Buyback data | AKShare `stock_repurchase_em()` | Tushare `repurchase` API | Tushare requires paid token for this data. AKShare is free and returns the same East Money data. |
| Buyback data | AKShare `stock_repurchase_em()` | Balance sheet `TREASURY_SHARES` column | `TREASURY_SHARES` is a stock (accumulated value), not a flow. Cannot compute annual buyback yield from it alone. `stock_repurchase_em()` provides actual transaction data with `已回购金额`. |
| NOPAT calculation | Derive from EBIT + tax rate | Tushare `fina_indicator` ROIC field | Tushare Pro's `fina_indicator` does include ROIC directly, but requires paid token. Deriving from free AKShare data is more aligned with project constraints. |
| Policy document processing | Reuse existing `pdf_processor.py` | New specialized processor | Policy PDFs are structurally similar to annual reports (text + tables). No need for a separate processor. Same chunking strategy works. |
| Composite Alpha weights | Fixed hardcoded weights | User-configurable weights via API | Out of scope per PROJECT.md. Fixed weights are transparent, auditable, and simpler to test. |
| scipy dependency | Add scipy >=1.15.0 | Implement linregress manually in numpy | Manual implementation of slope, intercept, r_value, p_value, std_err is error-prone and duplicates scipy's battle-tested code. scipy is a standard scientific Python dependency. |

## What NOT to Add

| Item | Why Not |
|------|---------|
| statsmodels | Overkill for simple trend regression. scipy sufficient. |
| scikit-learn | ML not needed. Alpha scoring uses fixed weights, not learned models. |
| New vector database | Qdrant already handles all RAG needs. |
| New LLM provider | DeepSeek handles policy text extraction well. |
| New message queue | Arq + Redis sufficient for task volume. |
| New web framework | FastAPI handles all routing needs. |
| graphviz / visualization libraries | Backend is API-only. Visualization is frontend responsibility. |
| xlrd / openpyxl | Policy documents are PDF, not Excel. PyMuPDF already handles PDF. |
| celery / rabbitmq | Out of scope per PROJECT.md. |
| Tushare Pro (paid features) | Project constraint: free data sources only. |

## Installation

```bash
# Add scipy for trend analysis (only new dependency)
cd stockvaluefinder
uv add "scipy>=1.15.0"

# Pin numpy explicitly (already installed as transitive dep, pin for stability)
uv add "numpy>=2.4.0"
```

## Existing Code Integration Points

### Services Layer Pattern (follow exactly)

The new services must follow the established pattern from `risk_service.py`, `valuation_service.py`, `yield_service.py`:

1. **Pure functions only** -- no class state, no side effects, no I/O
2. **Dict inputs** from financial data (not ORM models)
3. **Return frozen Pydantic models** with `model_config = {"frozen": True}`
4. **Audit trail dict** in results for transparency
5. **`calculate_*` naming** for pure functions, `analyze_*` for orchestrators

### External Data Service Extension Pattern

Add methods to `ExternalDataService` following the existing `get_financial_report` pattern:
1. Try AKShare first
2. Fallback to efinance/Tushare
3. Cache with Redis (24h TTL for financial data, 1h for buyback data)
4. Return normalized dict with `report_source` field

### ROIC-WACC Integration with Existing Valuation

The existing `calculate_wacc()` in `valuation_service.py` computes WACC via CAPM (Rf + beta * ERP). The ROIC-WACC spread calculation **must reuse this exact function** to ensure consistency. The ROIC service imports from valuation_service:

```python
from stockvaluefinder.services.valuation_service import calculate_wacc
```

This ensures WACC is computed identically for both DCF valuation and ROIC-WACC spread analysis.

### Policy Resonance: Qdrant Collection Setup

New collection `policy_documents` mirrors `annual_reports` setup:
- Same 1024-dim COSINE vectors (bge-m3)
- Payload indexes: `report_type` (KEYWORD), `policy_area` (KEYWORD), `effective_date` (INTEGER)
- No `ticker` or `year` indexes (policy docs are cross-company)

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| AKShare ROIC inputs (EBIT, tax, equity, debt) | HIGH | Verified live against 600519. All columns present and populated. |
| AKShare buyback data | HIGH | `stock_repurchase_em()` verified: returns 5088 stocks with `已回购金额`. Takes no arguments, filter in code. |
| AKShare CapEx proxy | HIGH | `CONSTRUCT_LONG_ASSET` verified in cash flow sheet. Standard CapEx proxy in Chinese accounting. |
| scipy for trend analysis | HIGH | Standard library, well-documented, `linregress` is battle-tested. |
| Qdrant separate collection approach | HIGH | Standard pattern, avoids schema pollution. Existing code supports multiple collections. |
| NOPAT derivation formula | MEDIUM | EBIT = TOTAL_PROFIT + FINANCE_EXPENSE works for non-financials. Financial sector companies (banks, insurance) need different handling (use OPERATE_PROFIT directly). Must add sector-aware logic. |
| Policy-to-DCF parameter extraction via LLM | MEDIUM | DeepSeek can extract structured parameters from Chinese policy text, but extraction quality depends on prompt engineering. Needs testing with real policy documents. |
| Composite Alpha fixed weights | HIGH | Academic backing for component selection. Weights are product decisions, not technical constraints. |

## Sources

- AKShare v1.18.46 installed and verified live
- `stock_profit_sheet_by_report_em` column verification: TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX confirmed for 600519
- `stock_balance_sheet_by_report_em` column verification: TOTAL_PARENT_EQUITY, SHORT_LOAN, LONG_LOAN, BOND_PAYABLE, TREASURY_SHARES confirmed
- `stock_cash_flow_sheet_by_report_em` column verification: NETCASH_OPERATE, CONSTRUCT_LONG_ASSET confirmed
- `stock_repurchase_em()` verified: returns DataFrame with 5088 rows, columns include `股票代码`, `已回购金额`, `已回购股份数量`
- scipy linregress documentation: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html
- Existing codebase: `valuation_service.py` WACC calculation, `risk_service.py` pure function pattern, `data_service.py` fallback chain, `vector_store.py` Qdrant multi-collection support, `retriever.py` SemanticRetriever search interface
