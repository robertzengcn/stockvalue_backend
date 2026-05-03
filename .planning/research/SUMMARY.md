# Research Summary: StockValueFinder v1.2 Alpha Engine

**Domain:** Financial analysis platform -- value investing decision support
**Researched:** 2026-05-03
**Overall confidence:** HIGH

## Executive Summary

The v1.2 Alpha Engine milestone adds four forward-looking analysis capabilities to the existing backward-looking audit system. The core finding is that **zero new infrastructure is required** -- all four features integrate into the existing FastAPI/PostgreSQL/Qdrant/Redis stack. The only new library dependency is scipy (for trend line regression on 3-year ROIC-WACC spreads).

The most critical technical decision is how ROIC inputs are derived. AKShare does not provide ROIC, NOPAT, or Invested Capital as pre-computed fields. Instead, these must be calculated from raw financial statement columns (TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX from the profit sheet; TOTAL_PARENT_EQUITY, SHORT_LOAN, LONG_LOAN, BOND_PAYABLE, TREASURY_SHARES from the balance sheet). All required columns were verified live against 600519 (Kweichow Moutai) data. The key caveat is that nan values appear for debt fields when a company carries no debt -- the code must normalize these to 0.0.

The Policy Resonance Engine reuses the entire existing RAG pipeline (PDF upload, PyMuPDF extraction, bge-m3 embedding, Qdrant storage, SemanticRetriever search) with a single architectural change: policy documents go into a separate Qdrant collection (`policy_documents`) because they lack ticker/year metadata that annual reports have. The DeepSeek LLM then extracts structured DCF parameter adjustments from the matched policy text.

The Capital Allocation scorecard relies on AKShare's `stock_repurchase_em()` function (verified: returns 5088 stocks with buyback amounts) and the existing dividend history API plus the `CONSTRUCT_LONG_ASSET` cash flow column (standard CapEx proxy in Chinese accounting). The Composite Alpha score is a straightforward weighted sum with hardcoded weights.

## Key Findings

**Stack:** Only 1 new dependency needed (scipy >=1.15.0 for linregress). numpy already installed. Zero new infrastructure.
**Architecture:** All new services follow existing pure-function pattern. 3 new ORM models, 1 Alembic migration, 1 new API route file, separate Qdrant collection for policy docs.
**Critical pitfall:** NOPAT derivation must handle financial sector companies differently (use OPERATE_PROFIT instead of TOTAL_PROFIT + FINANCE_EXPENSE). AKShare debt columns return nan for debt-free companies.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **ROIC-WACC Spread Analysis** -- Foundation for everything else
   - Addresses: ROIC calculation, WACC reuse, 3-year trend detection
   - Avoids: Building other features on untested ROIC inputs
   - Adds: scipy dependency, akshare_client extension, roic_service, roic model/repo

2. **Capital Allocation Scorecard** -- Depends on ROIC for blind expansion detection
   - Addresses: Buyback yield, dividend stability, CapEx surge, blind expansion alerts
   - Depends on: Phase 1 (ROIC < WACC check in blind expansion detection)
   - Adds: akshare_client.get_repurchase_data(), capital_allocation_service

3. **Policy Resonance Engine** -- Independent of financial calculations
   - Addresses: Policy doc upload, vector matching, DCF parameter extraction
   - Can be developed in parallel with Phase 2
   - Adds: Separate Qdrant collection, policy_resonance_service, new prompt templates

4. **Composite Alpha Score + API Integration** -- Depends on all above
   - Addresses: Weighted scoring, unified API endpoint, persistence
   - Depends on: Phases 1, 2, 3 (all component scores)
   - Adds: alpha_composite_service, alpha_routes, alpha ORM models, Alembic migration

**Phase ordering rationale:**
- ROIC-WACC must come first because Capital Allocation's "blind expansion" detection requires knowing whether ROIC < WACC
- Policy Resonance can parallel Phase 2 since it has no data dependency on financial calculations
- Composite Alpha must come last because it aggregates scores from the three other components

**Research flags for phases:**
- Phase 1: Financial sector NOPAT handling needs careful design (sector detection + formula branching)
- Phase 2: `stock_repurchase_em()` returns ALL stocks -- caching strategy for filtered subset matters
- Phase 3: LLM prompt engineering for DCF parameter extraction needs iterative testing with real policy documents
- Phase 4: Straightforward aggregation, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only scipy needed. All other components verified in existing codebase. |
| Features | HIGH | All AKShare data sources verified live. All formulas are standard financial analysis. |
| Architecture | HIGH | Follows established patterns (pure functions, frozen models, repository pattern). |
| Pitfalls | MEDIUM | Financial sector NOPAT handling is a known gap. LLM extraction quality is untested. |

## Gaps to Address

- Financial sector (banks, insurance, securities) NOPAT derivation needs sector-aware logic -- must detect sector from stock metadata and apply correct formula
- `stock_repurchase_em()` returns a large dataset (5088 rows) -- need efficient filtering and caching strategy, not re-fetching per stock
- LLM prompt for DCF parameter extraction from policy text needs iterative testing with real Chinese government policy documents (e.g., "十四五规划", "新能源汽车补贴政策")
- No pre-computed ROIC data source available for free -- Tushare Pro has it but requires paid token, which is out of scope
