# Pitfalls Research

**Domain:** AI-enhanced value investment analysis platform (A-share / HK stock)
**Researched:** 2026-04-14
**Confidence:** HIGH (codebase-verified + domain research)

## Critical Pitfalls

Mistakes that would cause rewrites, produce wrong financial results, or silently corrupt analysis output.

---

### Pitfall 1: M-Score Produces Meaningless Results With Hardcoded Indices

**What goes wrong:**
All 8 Beneish M-Score component indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) are hardcoded to 1.0/0.0 defaults in `data_service.py` across all three data source paths (AKShare, efinance, Tushare). The `risk_service.py` formula applies correct Beneish coefficients to these fake inputs, producing an M-Score that looks plausible (-4.84 + weighted sums of 1.0) but is entirely fictitious. Users making investment decisions based on these numbers would be misled.

**Why it happens:**
The formula implementation in `risk_service.py` was written correctly (lines 58-68), but the upstream data extraction in `data_service.py` (lines 895-902 for AKShare, 952-959 for efinance, 1021-1030 for Tushare) never calculates the actual year-over-year index ratios. Each index requires dividing current-year values by previous-year values (e.g., DSRI = (receivables_t / revenue_t) / (receivables_t-1 / revenue_t-1)). This requires fetching and cross-referencing two years of granular balance-sheet and income-statement line items, which was deferred as a TODO.

**How to avoid:**
1. Implement a dedicated `calculate_mscore_indices(current, previous) -> dict` pure function in `risk_service.py` that computes all 8 indices from raw financial fields.
2. Remove the hardcoded index fields from `data_service.py` entirely -- the data layer should return raw fields (accounts_receivable, revenue, gross_margin, etc.), not pre-computed indices.
3. Move index calculation into `analyze_financial_risk()` in `risk_service.py` where both current and previous data are available.
4. Add property-based tests verifying that when current == previous, all indices equal 1.0, and M-Score equals a known baseline.

**Warning signs:**
- M-Score for every stock clusters near the same value (~-4.2).
- All DSRI, GMI, AQI values are exactly 1.0 in database.
- No test exercises M-Score with actual year-over-year index calculation.
- Comments say "Note: M-Score indices need to be calculated separately" (found in `data_service.py:894`).

**Phase to address:**
Phase 1 (M-Score Index Calculation) -- this is the highest-priority item because the core fraud-detection output is currently meaningless.

---

### Pitfall 2: Multi-Agent Orchestration Over-Engineering

**What goes wrong:**
Research shows 41-87% of multi-agent LLM systems fail in production, with cascading coordination errors compounding across agents (the "17x error trap"). For this codebase, the planned coordinator + risk + valuation + yield agent architecture (4 agents in `stockvaluefinder/agents/`) risks introducing more failure points than the current sequential route-level approach. Agents can produce conflicting conclusions (e.g., risk agent flags HIGH risk but valuation agent gives strong BUY), goal-drift where agents optimize locally rather than globally, and state-passing errors where one agent's output schema does not match another's input expectations.

**Why it happens:**
Multi-agent systems are architecturally seductive. The existing codebase already has clean separation of concerns (risk_service, valuation_service, yield_service are pure functions). Replacing the route-level orchestration with a LangGraph StateGraph adds complexity without proportional benefit when each "agent" is just calling a deterministic calculation function and then generating a narrative.

**How to avoid:**
1. Start with a single-coordinator pattern: one agent that calls deterministic tools (the existing pure functions), not four independent agents communicating with each other.
2. Use LangGraph only for state management and validation loops, not for inter-agent message passing.
3. Define a strict typed state schema (`TypedDict` or Pydantic model) that all nodes consume and produce, preventing schema mismatches.
4. Add validation gates between steps: validate data quality before calculation, validate calculation results before narrative generation.
5. Keep the existing pure-function services (`risk_service.py`, `valuation_service.py`, `yield_service.py`) as the deterministic tools the agent calls. Do NOT wrap them in agent abstractions.

**Warning signs:**
- Agent output schema changes break downstream agents silently.
- Debugging requires tracing through 4+ agent conversation logs.
- Analysis latency increases dramatically (each agent = LLM call).
- Test coverage drops because multi-agent flows are hard to unit-test.

**Phase to address:**
Phase for agent orchestration -- design the coordinator as a single agent with tool calls first; only split into multiple agents if the coordinator becomes genuinely complex (unlikely for CSI 300 batch reports).

---

### Pitfall 3: RAG Pipeline Destroys Financial Table Structure

**What goes wrong:**
Chinese annual reports contain dense financial tables (balance sheets, income statements, cash flow statements) with multi-row headers, merged cells, and precise numerical data. Fixed-size chunking (e.g., 500-token windows) splits mid-table, destroying row-column relationships. When BGE-M3 embeds these fragments, vector similarity search returns table fragments without context, and the LLM either hallucinates missing values or retrieves the wrong period's data. For a fraud-detection system, this means the RAG may serve incorrect financial figures into analysis.

**Why it happens:**
Standard RAG tutorials use fixed-size chunking for prose documents. Financial reports are fundamentally different: they are structured data (tables) embedded in prose (MD&A, auditor notes). The CLAUDE.md specifies "Parent-Document Retrieval: 500-token chunks for search, return 2000-token parent context," but 500-token chunks will still cut across table rows. Chinese annual reports also mix simplified Chinese accounting terminology that BGE-M3 may not segment optimally without careful configuration.

**How to avoid:**
1. Use structure-aware chunking: parse tables separately from prose. Each complete financial table = one chunk. Prose sections (MD&A, auditor opinion) = separate chunks.
2. For table chunks, embed the table title + column headers + row labels as a single unit, not individual cells.
3. Store chunk metadata (fiscal_year, report_type, page_number) in Qdrant payload for pre-filtering before vector search. Never return data from the wrong year.
4. Use BGE-M3's multi-vector (ColBERT) mode for financial documents, which handles token-level matching better than dense-only retrieval for numerical data.
5. Implement a verification step: after RAG retrieval, cross-check retrieved figures against structured data from AKShare/efinance. Never trust RAG-retrieved numbers as the sole source for calculations.

**Warning signs:**
- RAG returns financial figures that do not match known data.
- Retrieved chunks contain half a table (missing columns/rows).
- Users report analysis based on wrong-year data.
- Embedding dimension mismatch between BGE-M3 output and Qdrant collection config.

**Phase to address:**
Phase for RAG pipeline -- table-aware chunking must be designed from day one, not retrofitted after basic RAG is "working."

---

### Pitfall 4: Redis Cache Serves Stale Financial Data After Corporate Events

**What goes wrong:**
The planned cache TTLs (financial reports: 24h, prices: 5min, rates: 1h) work for normal market conditions but become dangerous during corporate events. A company restates earnings, issues a profit warning, or releases an updated annual report, and the 24-hour cached report continues serving the old (now incorrect) financial data. For a fraud-detection platform, serving stale financials could mean missing a newly-detected anomaly or flagging a stock based on superseded data. The existing `CacheManager` in `utils/cache.py` has no invalidation mechanism tied to corporate events or data-source updates.

**Why it happens:**
TTL-based caching is simple to implement but assumes data changes at a predictable rate. Financial data is bursty: static for months, then a single filing changes everything. The current cache decorator pattern (`cache_result` in `cache.py`) has no way to know when upstream data has changed.

**How to avoid:**
1. Implement cache key versioning that includes the report period: `financial_report:{ticker}:{fiscal_year}:{report_date}`. When AKShare returns a different `report_date` for the same period, the cache miss triggers automatically.
2. Add an explicit cache invalidation endpoint or function that clears cached data for a specific ticker when a new filing is detected.
3. For price data, use a hybrid approach: serve from cache if age < TTL, but refresh asynchronously. Never block analysis on a stale cache hit when fresh data is available.
4. Always include a `cached_at` timestamp in cached data so consumers know how stale the data is.
5. When the risk analysis or valuation detects anomalous results (M-Score jump > 2 standard deviations from prior), bypass cache and force fresh data fetch.

**Warning signs:**
- Analysis results do not change even after new filings are known to be published.
- `cached_at` timestamp is > 24h old for a ticker that had recent news.
- `delete_by_pattern` is called frequently as a workaround for stale data.

**Phase to address:**
Phase for Redis caching integration -- design cache keys and invalidation strategy before writing any cache code.

---

### Pitfall 5: AKShare Field Name Changes Silently Break Data Extraction

**What goes wrong:**
The `data_service.py` file (1187 lines) tries multiple field names for each metric in a fallback chain (e.g., lines 552-573 try 5 different field names for operating cash flow). When AKShare or its upstream data source (East Money) silently changes a column name, the code falls through to returning 0.0 for that field. This is catastrophic for calculations: a missing `accounts_receivable` value becoming 0.0 makes DSRI = 0, which makes the M-Score misleading. There is no validation that a critical field was actually found versus defaulted to zero.

**Why it happens:**
AKShare does not follow semantic versioning or provide formal deprecation cycles. The upstream data providers (East Money, Sina Finance) change their web APIs without notice, which causes AKShare maintainers to rename fields in patches. The codebase tries to be resilient by checking multiple field names, but the fallback to 0.0 is silent and dangerous.

**How to avoid:**
1. Add explicit field validation after extraction: if a critical field (revenue, net_income, accounts_receivable, total_assets, operating_cash_flow) is not found in the API response, raise `DataValidationError` with the field name and available keys. Do not silently default to 0.
2. Pin AKShare version in `pyproject.toml` and test against the pinned version.
3. Add a schema validation layer using Pydantic: define `AKShareFinancialReport` model with required fields, and validate API responses against it before passing to calculations.
4. Create a "data quality health check" endpoint that verifies a known stock (e.g., 600519.SH / Kweichow Moutai) returns expected fields. Run this as a smoke test.
5. Monitor AKShare GitHub releases and pin to specific commits if necessary for production stability.

**Warning signs:**
- Many financial fields return exactly 0.0 for stocks that should have data.
- AKShare version is unpinned or uses `>=` in dependencies.
- No error logged when a field falls through all name variants to default.
- Test coverage for data_service.py only tests happy-path with mocked data.

**Phase to address:**
Phase 1 (immediately) -- add field validation to `data_service.py` before any M-Score calculation is meaningful.

---

### Pitfall 6: FCF Calculation Uses Inconsistent CapEx Sign Convention

**What goes wrong:**
`data_service.py` line 576 uses `fcf = ocf - abs(capex)` for AKShare data, assuming capex is positive. Line 607 uses `fcf = ocf + capex` for Tushare data, assuming capex is negative (cash outflow). If either data source changes its sign convention (or if efinance uses yet another convention), the FCF calculation will be silently wrong, producing negative FCF for companies with positive cash generation. This directly feeds into DCF valuation, making intrinsic value calculations unreliable.

**Why it happens:**
Different Chinese financial data providers report capital expenditure with different sign conventions. AKShare/efinance typically report capex as a positive expenditure amount, while Tushare follows the cash flow statement convention where capex is negative (representing cash outflow). The code hardcodes the sign handling per source rather than normalizing upstream.

**How to avoid:**
1. Normalize all financial data to a canonical sign convention in the data client layer (AKShare client, efinance client, Tushare client), not in the service layer.
2. Document the canonical convention in a module-level docstring: e.g., "All monetary flows: positive = inflow, negative = outflow."
3. Add unit tests for each data client that verify capex sign after normalization.
4. Add a cross-validation check: if FCF from different sources for the same stock differs by more than 10%, log a warning.

**Warning signs:**
- FCF is always negative or always positive regardless of company.
- Switching primary data source (AKShare to efinance) changes DCF results dramatically.
- No tests for FCF calculation with actual data source responses.

**Phase to address:**
Phase 1 -- normalize data in the client layer before M-Score calculation work begins.

---

### Pitfall 7: LLM Narrative Hallucination Overwrites Deterministic Results

**What goes wrong:**
The LLM (DeepSeek) generates Chinese-language narratives explaining analysis results. Currently, the narrative is clearly separated from calculation results and gracefully returns None on failure. However, as the system evolves toward multi-agent orchestration, there is a risk that LLM-generated content could be incorrectly treated as authoritative analysis rather than explanation. More subtly, the LLM narrative might contradict the deterministic calculation results (e.g., the M-Score indicates LOW risk but the narrative says "shows significant manipulation risk"). For a platform positioning itself as an "investment auxiliary tool," contradictory output undermines credibility.

**Why it happens:**
LLMs are trained to produce fluent text, not to faithfully reproduce numerical analysis. When an LLM receives structured financial data in a prompt, it may "interpret" the numbers differently than the deterministic formulas, especially for edge cases or when the prompt is ambiguous. The existing `build_risk_prompt` and `build_dcf_explanation_prompt` functions in `narrative_prompts.py` must be carefully crafted to prevent this.

**How to avoid:**
1. Always include the deterministic result values explicitly in the LLM prompt: "The M-Score is -2.45, which indicates LOW risk (threshold: -1.78). Generate a narrative explaining this result."
2. Never ask the LLM to interpret raw financial data independently -- always pass pre-calculated results.
3. Add a post-generation validation step: parse the narrative and verify key numbers mentioned match the deterministic results. Flag contradictions.
4. Clearly label all LLM output as "AI-generated analysis summary" in the API response, distinct from the deterministic calculation results.
5. Add a `confidence_note` field to narratives: "This narrative is generated by AI and summarizes pre-calculated financial metrics."

**Warning signs:**
- Narrative contradicts the `risk_level` field in the response.
- LLM mentions different numerical values than what is in the calculation output.
- Narrative quality degrades when switching LLM providers.

**Phase to address:**
Every phase that involves LLM narrative generation -- add prompt validation and output verification from the start.

---

### Pitfall 8: Hardcoded Database Credentials in Source Code

**What goes wrong:**
`db/base.py` line 17 contains a hardcoded PostgreSQL connection string with username and password as a fallback default: `postgresql+asyncpg://svf_admin:Fo41_2vhaOHKnBAyMUToMA@localhost:5433/stockvaluefinder`. This credential is committed to git history. If the repository is ever made public or shared, the database is compromised. Even for a private repo, this practice means:
- Different environments (dev, staging, production) cannot use different credentials without code changes.
- CI/CD pipelines may accidentally expose credentials in logs.
- Rotating the password requires a code change, not just a config change.

**Why it happens:**
Convenience during early development. The `os.environ.get("DATABASE_URL", hardcoded_fallback)` pattern is common in tutorials but unacceptable in production.

**How to avoid:**
1. Remove the hardcoded fallback entirely. Use `os.environ.get("DATABASE_URL")` with no default, and fail fast with a clear error message if the variable is unset.
2. Add a `.env.example` file (committed to git) showing required variables without actual values.
3. Ensure `.env` is in `.gitignore` (verify it is).
4. Rotate the currently exposed password immediately.
5. Add a startup validation check that verifies all required environment variables are set before the application starts accepting requests.

**Warning signs:**
- `DATABASE_URL` in `.env` differs from the hardcoded fallback, causing confusion.
- Docker Compose or CI uses the hardcoded credential instead of environment variables.
- `git log` shows the credential in commit history.

**Phase to address:**
Phase 0 (pre-requisite, before any milestone work) -- this is a security fix that should happen immediately.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded M-Score indices (1.0/0.0 defaults) | Ship risk API with formula in place | Meaningless analysis results; users lose trust in the platform | Never -- this is the core value proposition |
| God routes (risk_routes.py fetches, analyzes, narrates, saves) | Fast iteration, all logic visible in one place | Impossible to test independently; route changes break save logic | Only for MVP if tests exist; extract orchestrator layer before adding agents |
| Module-level singleton for NarrativeService | Simple access from any route | Hard to test (requires `reset_narrative_service()`); hidden global state | Acceptable if dependency injection is added later |
| Static fallback rates in rate_client.py | System works without network access | Stale rates produce wrong WACC, wrong yield gap; no warning to users | Acceptable only as last-resort fallback with clear "stale data" warning in response |
| No schema validation on external API responses | Flexible, handles any data format | Silent data loss when field names change; 0.0 defaults hide errors | Never for financial data -- validate at system boundaries |
| Sequential data fetches in risk_routes.py | Simpler code | 2x latency for risk analysis (current + previous report fetched sequentially) | Acceptable for MVP (<300 stocks); must parallelize before batch processing |
| ThreadPoolExecutor per RateClient instance | Simple async wrapper | Connection/resource leak; no pooling across requests | Only until Redis caching is integrated |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AKShare | Assuming field names are stable across versions | Pin version; validate response schema; maintain field-name mapping config |
| AKShare | Server-side blocking when deployed (Issue #7005) | Use request throttling; rotate User-Agent; implement circuit breaker |
| efinance | Assuming efinance returns same format as AKShare | Each client normalizes to canonical format independently |
| Tushare | Assuming free-tier has all data access | Check Tushare permission levels; graceful degradation to AKShare |
| DeepSeek LLM | Sending raw numbers in prompt without context | Format numbers with units and labels; include calculation methodology in system prompt |
| Qdrant | Creating collection without configuring distance metric and vector size | Pre-configure collection with BGE-M3 dimensions (1024) and Cosine distance |
| Redis | Using same TTL for all data types | Tier TTLs by data volatility: prices 5min, rates 1h, reports 24h, narratives never |
| PostgreSQL | Auto-commit in get_db() dependency (line 44 of db/base.py) + manual commit in routes | Risk routes call `db.commit()` after `get_db` already commits on exit. Use explicit transaction boundaries |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential external API calls per analysis request | Risk analysis takes 8-12 seconds (2 report fetches + price + rate + narrative + DB save) | Use `asyncio.gather` for independent fetches (valuation_routes already does this correctly); cache aggressively | At >10 concurrent users or batch processing of CSI 300 |
| No connection pooling for external HTTP clients | RateClient creates new httpx.AsyncClient per request; AKShare runs in new ThreadPoolExecutor each time | Create shared client instances at application startup; reuse connection pools | At >50 requests/minute |
| Qdrant full-collection scan without metadata pre-filtering | Vector search returns irrelevant chunks; query latency increases linearly with collection size | Use Qdrant payload filters (year, industry, ticker) before vector search | At >1000 documents (about 10 annual reports) |
| LLM narrative generation blocks response | User waits 3-5 extra seconds for narrative; DeepSeek API timeout cascades | Generate narrative asynchronously; return analysis results immediately, narrative via callback or polling | At first deployment with real users |
| Cache stampede after TTL expiry | Multiple requests for same stock all bypass cache simultaneously, hammering AKShare | Use cache lock pattern: first request refreshes, others serve stale data briefly | At >5 concurrent requests for same stock |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Hardcoded DB credentials in source code (db/base.py:17) | Database compromise if repo is leaked; credential rotation requires code change | Environment-variable-only config; fail fast on missing vars; rotate exposed password |
| No rate limiting on analysis endpoints | Single user can trigger thousands of external API calls, causing IP ban from AKShare/East Money | Add per-IP rate limiting (e.g., 60 requests/minute); queue batch requests |
| LLM prompt injection via stock ticker | Malicious ticker input (though regex-validated to 6 digits + exchange) could be crafted to manipulate narrative generation | Validate input before including in prompts; sanitize all user-provided strings in prompts |
| No audit trail for analysis results | Users cannot verify which data source/version produced a result; regulatory risk for "investment auxiliary tool" | Store data_source, data_fetched_at, and calculation_parameters with every analysis result |
| CORS allows all headers and methods on localhost | Acceptable for dev but dangerous if deployed with these settings | Restrict CORS to specific origins, methods, and headers for production |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Analysis returns M-Score with hardcoded indices | User sees "LOW risk" for a stock that should be flagged; financial loss if they trust the result | Show "M-Score calculation pending" or "Preliminary result" until real indices are computed; add confidence indicator |
| Stale cached data served without indication | User thinks they are seeing today's data but it is from yesterday; misses time-sensitive information | Include `data_as_of` timestamp in every response; show warning when data is >24h old |
| LLM narrative contradicts numerical result | User is confused: numbers say one thing, text says another; loses trust in platform | Add validation layer comparing narrative claims to calculation output; flag contradictions |
| No progress feedback for batch analysis | User triggers CSI 300 scan, sees nothing for 30+ minutes, thinks it is broken | Add job queue with progress tracking; show per-stock completion status |
| Error messages do not distinguish "no data" from "system error" | User does not know whether to retry or report a bug | Return distinct error codes: DATA_NOT_FOUND, EXTERNAL_API_ERROR, CALCULATION_ERROR, etc. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **M-Score calculation:** Formula is implemented but 8 input indices are hardcoded -- verify indices are calculated from raw financial data, not defaults
- [ ] **Redis caching:** CacheManager is implemented but never integrated -- verify cache is actually called in data fetch paths, not just importable
- [ ] **RAG pipeline:** 4 module files exist (vector_store, retriever, embeddings, pdf_processor) but all are stubs -- verify each has actual implementation, not just class definitions with TODO
- [ ] **Agent orchestration:** 4 agent files exist (coordinator, risk, valuation, yield) but all are stubs -- verify agents have LangGraph StateGraph definitions, not just empty classes
- [ ] **Calculation sandbox:** File exists but raises NotImplementedError -- verify subprocess execution works with resource limits before trusting it for production calculations
- [ ] **Test coverage:** Unit tests exist for risk_service but integration tests for routes are unimplemented -- verify conftest.py has working DB session fixture, not just NotImplementedError
- [ ] **Application lifespan:** main.py has 5 TODOs for startup/shutdown -- verify Redis, Qdrant, and DB connections are initialized/closed properly
- [ ] **LLM provider config:** narrative_service.py hardcodes `provider="deepseek"` -- verify provider is configurable via environment variable
- [ ] **Database migrations:** Alembic migrations exist but no CI verification -- verify migrations run cleanly from scratch on empty database

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| M-Score hardcoded indices | MEDIUM | 1. Implement index calculation function. 2. Backfill existing risk_score rows with recalculated values. 3. Add migration to mark old results as "preliminary." |
| Multi-agent over-engineering | HIGH | 1. Replace multi-agent with single coordinator + tool calls. 2. Reuse existing pure-function services as tools. 3. Keep agent interface thin. |
| RAG table structure destroyed | MEDIUM | 1. Re-chunk documents with structure-aware parser. 2. Re-embed all documents. 3. Clear Qdrant collection and re-ingest. |
| Stale cache served | LOW | 1. Add cache-bypass header/parameter to analysis endpoints. 2. Implement forced-refresh endpoint. 3. Add `cached_at` to all cached responses. |
| AKShare field name change | LOW | 1. Pin AKShare version. 2. Add field validation layer. 3. Monitor AKShare changelog. |
| FCF sign convention error | MEDIUM | 1. Normalize in client layer. 2. Recalculate affected valuations. 3. Add cross-source validation. |
| LLM narrative hallucination | LOW | 1. Tighten prompt instructions. 2. Add post-generation validation. 3. Flag contradictions for review. |
| Database credential exposure | HIGH | 1. Rotate password immediately. 2. Remove hardcoded value from code. 3. Use git-filter-branch or BFG to scrub history. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Hardcoded DB credentials (Pitfall 8) | Phase 0: Security hardening | `grep -r "postgresql://" stockvaluefinder/` returns no results; app fails to start without DATABASE_URL env var |
| M-Score hardcoded indices (Pitfall 1) | Phase 1: M-Score index calculation | Unit test: known stock (600519.SH) produces M-Score matching manual calculation; indices are not all 1.0 |
| AKShare field validation (Pitfall 5) | Phase 1: Data quality layer | Integration test: fetching 600519.SH returns all required fields; missing field raises DataValidationError |
| FCF sign convention (Pitfall 6) | Phase 1: Data normalization | Unit test: FCF from AKShare and Tushare for same stock agree within 5% |
| Redis cache invalidation (Pitfall 4) | Phase 2: Cache integration | Test: after cache set, new filing for same stock triggers cache miss; cached_at is included in response |
| Sequential fetches (performance) | Phase 2: Cache + parallelization | Benchmark: risk analysis completes in <3 seconds with warm cache; route uses asyncio.gather |
| LLM narrative validation (Pitfall 7) | Phase 2: Narrative quality | Test: narrative mentions same risk_level as calculation result; contradiction count = 0 in test set |
| RAG table chunking (Pitfall 3) | Phase 3: RAG pipeline | Test: retrieve specific financial figure from annual report; verify figure matches structured data source |
| Multi-agent architecture (Pitfall 2) | Phase 4: Agent orchestration | Test: coordinator produces same results as sequential route approach; no schema mismatch errors |

## Sources

- Kapa.ai: [RAG Gone Wrong: 7 Most Common Mistakes](https://www.kapa.ai/blog/rag-gone-wrong-the-7-most-common-mistakes-and-how-to-avoid-them)
- VentureBeat: [Most RAG Systems Don't Understand Sophisticated Documents](https://venturebeat.com/orchestration/most-rag-systems-dont-understand-documents-they-shred-them)
- Towards Data Science: [Why Your Multi-Agent System is Failing: Escaping the 17x Error Trap](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/)
- Augment Code: [Why Multi-Agent LLM Systems Fail (and How to Fix Them)](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them) -- 41-87% failure rate
- arXiv: [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/html/2503.13657v1)
- LangChain Blog: [How and When to Build Multi-Agent Systems](https://blog.langchain.com/how-and-when-to-build-multi-agent-systems/)
- Medium (TurkishTechnology): [Building a Self-Correcting Financial Analysis Agent](https://medium.com/@turkishtechnology/building-a-self-correcting-financial-analysis-agent-for-aviation-a-deep-dive-into-ebfa6ece5208)
- Precanto: [Enhancing Determinism in LLM Responses for Financial Data](https://precanto.com/blogs/enhancing-determinism-in-llm-responses-for-financial-data-strategies-to-reduce-hallucinations-and-ensure-reliable-insights)
- Redis.io Blog: [Three Ways to Maintain Cache Consistency](https://redis.io/blog/three-ways-to-maintain-cache-consistency/)
- LinkedIn: [Cache Invalidation in Financial Systems: The Hidden Performance Problem](https://www.linkedin.com/posts/fru-kerick_caching-fixed-our-performance-problem-then-activity-7437541152741928960-SDd8)
- AKShare GitHub: [Issue #7005 - Server detection blocking](https://github.com/akfamily/akshare/issues/7005)
- AKShare GitHub: [Issue #6986 - East Money interface issues](https://github.com/akfamily/akshare/issues/6986)
- ClawTrust: [AKShare Finance Evaluation](https://www.clawtrust.net/skills/benangel65/akshare-finance) -- breaking changes warning
- Investopedia: [Beneish Model Definition and M-Score Calculation](https://www.investopedia.com/terms/b/beneishmodel.asp)
- StableBread: [How to Use the Beneish M-Score](https://stablebread.com/beneish-m-score/)
- Qdrant: [Vector Search in Production](https://qdrant.tech/articles/vector-search-production/)
- Zhihu: [BGE-M3 Model Introduction](https://zhuanlan.zhihu.com/p/680537154) -- multi-function, 8192 token context
- arXiv: [FinCPRG: Chinese Financial Passage Retrieval](https://arxiv.org/html/2508.02222v1)
- Codebase analysis: risk_service.py, data_service.py, cache.py, db/base.py, narrative_service.py, risk_routes.py, main.py, conftest.py

---
*Pitfalls research for: AI-enhanced value investment analysis platform (A-share / HK stock)*
*Researched: 2026-04-14*
