# Architecture Patterns

**Domain:** Financial analysis platform -- Alpha Engine V2.0
**Researched:** 2026-05-03

## Recommended Architecture

The Alpha Engine extends the existing layered architecture without structural changes. New components plug into the established API -> Service -> Repository -> External/DB layers.

```
Existing Architecture (unchanged):
  API Routes -> Services (pure) -> Repositories -> DB/External
  
New Alpha Engine additions:
  alpha_routes.py -> roic_service.py (pure)
                  -> capital_allocation_service.py (pure)
                  -> policy_resonance_service.py (uses RAG)
                  -> alpha_composite_service.py (pure aggregator)
                  -> roic_repo.py -> PostgreSQL
                  -> capital_allocation_repo.py -> PostgreSQL
                  -> alpha_repo.py -> PostgreSQL
                  -> data_service.py (extended) -> AKShare/Redis
                  -> SemanticRetriever -> Qdrant (policy_documents collection)
                  -> DeepSeek LLM (policy extraction)
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `roic_service.py` | NOPAT, Invested Capital, ROIC, spread, trend calculations | valuation_service (WACC reuse), data_service (financial data) |
| `capital_allocation_service.py` | Buyback yield, dividend stability, CapEx surge, blind expansion detection | roic_service (ROIC < WACC check), data_service (buyback, dividend, CapEx data) |
| `policy_resonance_service.py` | Policy upload, vector matching, DCF parameter extraction | SemanticRetriever (Qdrant search), DeepSeek LLM (parameter extraction), pdf_processor (chunking) |
| `alpha_composite_service.py` | Weighted scoring aggregation | roic_service, capital_allocation_service, policy_resonance_service (component scores) |
| `alpha_routes.py` | HTTP API endpoints, request validation, response formatting | All services, repositories |
| `data_service.py` (extended) | ROIC inputs, buyback data, CapEx data fetching with caching | akshare_client, efinance_client, Redis cache |

### Data Flow

**ROIC-WACC Analysis Flow:**
```
User Request (ticker)
  -> alpha_routes.py: POST /api/v1/alpha/roic
  -> data_service.get_roic_inputs(ticker, fiscal_year)
      -> akshare_client.get_profit_sheet() -> TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX
      -> akshare_client.get_balance_sheet() -> TOTAL_PARENT_EQUITY, SHORT_LOAN, LONG_LOAN, BOND_PAYABLE, TREASURY_SHARES
      -> Cache in Redis (24h TTL)
  -> roic_service.calculate_nopat(ebit, tax_rate)
  -> roic_service.calculate_invested_capital(equity, debt, treasury_shares)
  -> roic_service.calculate_roic(nopat, invested_capital)
  -> valuation_service.calculate_wacc(risk_free_rate, beta, market_risk_premium)  [REUSE EXISTING]
  -> roic_service.calculate_roic_wacc_spread(roic, wacc)
  -> roic_service.analyze_roic_trend(3_year_spreads)  [scipy.stats.linregress]
  -> roic_repo.upsert(result)
  -> ApiResponse[ROICWACCSpread]
```

**Policy Resonance Flow:**
```
User Upload (policy PDF)
  -> alpha_routes.py: POST /api/v1/alpha/policy/upload
  -> pdf_processor.extract_pdf_content()  [REUSE EXISTING]
  -> pdf_processor.chunk_into_parents() / chunk_parents_into_children()  [REUSE EXISTING]
  -> BGEEmbeddingClient.generate_embeddings()  [REUSE EXISTING]
  -> QdrantVectorStore(collection="policy_documents").upsert_chunks()
  -> ApiResponse[DocumentUploadResponse]

User Match Request (ticker + industry)
  -> alpha_routes.py: POST /api/v1/alpha/policy/match
  -> policy_resonance_service.match_policy_to_stock(ticker, industry_keywords)
      -> SemanticRetriever.search(query=industry_keywords, collection="policy_documents")
  -> policy_resonance_service.extract_dcf_adjustments(matched_policy_text)
      -> DeepSeek LLM -> structured DCFAdjustment (terminal_growth_delta, risk_premium_delta)
  -> policy_resonance_service.calculate_policy_resonance_score(matches)
  -> ApiResponse[PolicyResonanceResult]
```

**Composite Alpha Flow:**
```
User Request (ticker)
  -> alpha_routes.py: POST /api/v1/alpha/composite
  -> roic_service -> ROIC-WACC score (0-100)
  -> capital_allocation_service -> Capital Allocation score (0-100)
  -> policy_resonance_service -> Policy Resonance score (0-100)
  -> roic_service.analyze_roic_trend() -> Moat trend score (0-100)
  -> alpha_composite_service.calculate_composite_alpha(scores, weights)
      -> 0.40 * roic_score + 0.30 * capital_score + 0.20 * policy_score + 0.10 * moat_score
  -> alpha_repo.upsert(result)
  -> ApiResponse[CompositeAlphaResult]
```

## Patterns to Follow

### Pattern 1: Pure Function Services (follow existing)

**What:** All financial calculations are stateless pure functions with dict inputs and frozen Pydantic model outputs.
**When:** All new service files.
**Why:** The existing codebase uses this pattern for risk_service, valuation_service, and yield_service. Consistency matters more than personal preference.

```python
# roic_service.py
def calculate_nopat(
    total_profit: float,
    finance_expense: float,
    income_tax: float,
) -> dict[str, float]:
    """Calculate NOPAT from income statement fields.

    Args:
        total_profit: Total profit before tax (TOTAL_PROFIT)
        finance_expense: Net finance expense (FINANCE_EXPENSE, negative = net income)
        income_tax: Income tax expense (INCOME_TAX)

    Returns:
        Dict with ebit, tax_rate, nopat keys
    """
    # ... pure calculation, no I/O, no side effects ...
    return {"ebit": ebit, "tax_rate": tax_rate, "nopat": nopat}
```

### Pattern 2: Frozen Config for Weights

**What:** Alpha scoring weights are defined in a frozen dataclass in config.py.
**When:** Any configurable constant.
**Why:** Follows existing pattern (ValuationConfig, RiskConfig, YieldConfig). Frozen ensures immutability. Singleton via AppConfig.

```python
@dataclass(frozen=True)
class AlphaConfig:
    ROIC_WACC_WEIGHT: float = 0.40
    CAPITAL_ALLOC_WEIGHT: float = 0.30
    POLICY_WEIGHT: float = 0.20
    MOAT_WEIGHT: float = 0.10
    MOAT_TREND_YEARS: int = 3
    BLIND_EXPANSION_CAPEX_THRESHOLD: float = 0.30
    DIVIDEND_STABILITY_YEARS: int = 5
```

### Pattern 3: WACC Reuse via Import

**What:** Import `calculate_wacc` from valuation_service rather than reimplementing.
**When:** ROIC-WACC spread calculation needs WACC.
**Why:** Ensures WACC is computed identically for DCF valuation and ROIC-WACC spread. Avoids divergence.

```python
from stockvaluefinder.services.valuation_service import calculate_wacc

# In ROIC analysis:
wacc = calculate_wacc(risk_free_rate, beta, market_risk_premium)
spread = roic - wacc
```

### Pattern 4: Separate Qdrant Collection per Document Type

**What:** Policy documents stored in `policy_documents` collection, not mixed with `annual_reports`.
**When:** Any new document type with different metadata schema.
**Why:** Policy docs lack ticker/year. Mixing would break existing filters.

```python
policy_store = QdrantVectorStore(
    url="http://localhost:6333",
    collection="policy_documents",  # Separate collection
)
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Duplicating WACC Calculation
**What:** Writing a separate WACC function in roic_service.py.
**Why bad:** WACC values would diverge between DCF valuation and ROIC-WACC spread. Users would see inconsistent results.
**Instead:** Import from valuation_service.

### Anti-Pattern 2: Mixing Policy and Annual Report Vectors
**What:** Storing policy document chunks in the `annual_reports` Qdrant collection.
**Why bad:** Policy docs have no ticker or year. Existing search filters (`ticker`, `year`) would fail. ChunkMetadata schema would need optional fields, breaking frozen dataclass.
**Instead:** Separate `policy_documents` collection.

### Anti-Pattern 3: Fetching stock_repurchase_em() Per Stock
**What:** Calling `stock_repurchase_em()` for every stock analysis request.
**Why bad:** Returns 5088 rows for ALL stocks. Fetching 5000+ rows to filter one stock is wasteful and slow.
**Instead:** Fetch once, cache the full dataset in Redis (1h TTL), filter in-memory.

### Anti-Pattern 4: Using nan Debt Values in ROIC Calculation
**What:** Passing AKShare nan values directly into Invested Capital calculation.
**Why bad:** Any arithmetic with nan produces nan. ROIC becomes nan. Entire analysis fails.
**Instead:** Normalize all debt fields: `debt = 0.0 if pandas.isna(raw_value) else float(raw_value)`.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| AKShare rate limits | Per-stock on-demand, 24h Redis cache | Batch prefetch CSI 300 on schedule | Regional cache layers, premium data sources |
| Qdrant policy search | Single collection, <1000 policy docs | Multiple collections by policy area | Distributed Qdrant cluster |
| ROIC calculation | <100ms per stock (pure math) | Same -- pure functions scale linearly | Pre-compute for all CSI 300, update quarterly |
| Composite Alpha | 4 sub-calculations per request | Parallel service calls | Batch pre-compute, cache in Redis |
| stock_repurchase_em() | Full fetch + filter, 1h cache | Same | Incremental updates, webhook from East Money |

## Sources

- Existing architecture: risk_service.py, valuation_service.py, yield_service.py patterns
- Existing RAG: vector_store.py, retriever.py, embeddings.py integration
- Existing data: data_service.py fallback chain, akshare_client.py, Redis caching pattern
- AKShare v1.18.46 verified column names for all financial statement APIs
