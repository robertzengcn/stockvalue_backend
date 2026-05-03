# Pitfalls Research

**Domain:** Alpha Engine V2.0 (v1.2 milestone) -- ROIC-WACC spread analysis, capital allocation scorecard, policy resonance engine, composite Alpha scoring, moat trend detection, extending existing financial analysis platform (FastAPI + SQLAlchemy 2.0 + PostgreSQL + Qdrant + AKShare/efinance)
**Researched:** 2026-05-03
**Confidence:** HIGH (codebase-verified integration points + A-share domain knowledge + OECD composite indicator methodology)

## Critical Pitfalls

Mistakes that cause rewrites, incorrect financial results, or silent data corruption.

---

### Pitfall 1: ROIC Denominator (Invested Capital) Returns Negative -- Division Produces Misleading Positive Spread

**What goes wrong:**
ROIC = NOPAT / Invested Capital. For A-share companies with large negative net debt (cash exceeds debt), invested capital can be negative. This happens frequently for consumer brands like Maotai (600519.SH), which sit on enormous cash piles with minimal debt. A negative denominator with positive NOPAT produces a negative ROIC, which when subtracted from WACC, creates a large positive spread that incorrectly signals "value creation." The opposite case (negative NOPAT, negative invested capital) produces a positive ROIC that masks destruction.

**Why it happens:**
The formula `Invested Capital = Total Equity + Interest-Bearing Debt - Excess Cash` is standard in US textbooks, but A-share companies often hold cash far exceeding operational needs. The existing `valuation_service.py` uses `calculate_wacc` as a pure function with no awareness of invested capital at all -- it only computes cost of equity via CAPM. Developers implementing ROIC alongside this existing function will not encounter any guardrails.

**How to avoid:**
1. Define invested capital as `Total Equity + Interest-Bearing Debt - MIN(Cash, Operating Cash Requirement)`, where operating cash requirement is estimated as 2-5% of revenue. This prevents excess cash from flipping the denominator negative.
2. Add an explicit guard: if `invested_capital <= 0`, return `ROIC = None` with a `non_calculable` flag in the audit trail (follow the existing pattern from `risk_service.py:203-213` where `_safe_ratio` handles zero denominators).
3. Never compute ROIC-WACC spread when ROIC is `None` -- exclude the stock from moat trend analysis and set Alpha score component to neutral (0.5 normalized).
4. Document the threshold in a frozen dataclass config (following the `RiskConfig`/`ValuationConfig` pattern in `config.py`).

**Warning signs:**
- ROIC values exceeding 100% or below -100% for companies known to be stable.
- Maotai (600519.SH) shows negative invested capital in test data.
- ROIC-WACC spread calculation throws ZeroDivisionError in production.
- Moat trend shows sudden reversal for cash-rich companies.

**Phase to address:**
Phase 1 (ROIC-WACC Engine) -- the invested capital formula must be correct before any spread or trend computation.

---

### Pitfall 2: WACC Reuse Mismatch -- Existing Function Computes Ke Only, Not True WACC

**What goes wrong:**
The existing `valuation_service.py` implements `calculate_wacc` (lines 11-33) but it computes only the cost of equity: `WACC = Rf + beta * ERP`. This is the CAPM formula for Ke, not the true WACC formula which includes the after-tax cost of debt and capital structure weights: `WACC = E/(D+E) * Ke + D/(D+E) * Kd * (1-T)`. For the ROIC-WACC spread, using the existing "WACC" function as the hurdle rate understates the true cost of capital for leveraged companies and overstates it for cash-rich companies. The spread comparison becomes meaningless. If a developer copies the function into `roic_service.py` instead of importing it, the two analyses also diverge over time.

**Why it happens:**
The existing DCF model only uses the cost of equity as the discount rate (common simplification for equity valuation). The function is named `calculate_wacc` but the docstring says "Using CAPM: WACC = Rf + beta * ERP." When developers building ROIC-WACC look for a WACC function, they will find this one and reuse it without realizing it only computes Ke. The existing `ValuationConfig` has `DEFAULT_MARKET_RISK_PREMIUM` but no `COST_OF_DEBT` or `TAX_RATE` settings.

**How to avoid:**
1. Rename the existing function to `calculate_cost_of_equity` (or add an alias). Keep backward compatibility for the existing DCF pipeline.
2. Implement a new `calculate_true_wacc` function: `WACC = w_e * Ke + w_d * Kd * (1 - tax_rate)` where `w_e = equity / (debt + equity)`, `w_d = debt / (debt + equity)`, `Kd = interest_expense / interest_bearing_debt`.
3. Add `DEFAULT_COST_OF_DEBT`, `DEFAULT_TAX_RATE`, and `DEFAULT_TARGET_CAPITAL_STRUCTURE` to a new config class (e.g., `ROICConfig` frozen dataclass following the pattern in `config.py`).
4. Use `calculate_true_wacc` for the ROIC-WACC spread. Continue using `calculate_wacc` (Ke only) for the existing DCF pipeline to avoid breaking changes.
5. Import the function rather than duplicating it -- single source of truth.

**Warning signs:**
- ROIC-WACC spread shows identical values for highly leveraged and unleveraged companies in the same industry.
- The "WACC" value returned by ROIC analysis matches the cost of equity from DCF analysis exactly (should differ for companies with significant debt).
- Companies with 50%+ debt-to-equity ratios show the same WACC as companies with no debt.

**Phase to address:**
Phase 1 (ROIC-WACC Engine) -- the true WACC function must be implemented before any spread calculation.

---

### Pitfall 3: Financial Sector NOPAT Formula Mismatch

**What goes wrong:**
The standard NOPAT formula (EBIT = TOTAL_PROFIT + FINANCE_EXPENSE) is wrong for banks, insurance companies, and securities firms. For these companies, interest income/expense is a core operating item, not a financing item. Adding FINANCE_EXPENSE back to TOTAL_PROFIT double-counts operating income. CSI 300 includes many financial companies (ICBC, Ping An, CITIC Securities). Applying the non-financial NOPAT formula to financials produces artificially high ROIC.

**Why it happens:**
ROIC is designed for non-financial companies. The data extraction layer in `data_service.py` standardizes all financial data using the same field mapping regardless of industry. There is no industry-aware logic in the existing extraction code.

**How to avoid:**
1. Detect financial sector from stock metadata (the `stocks` table has a `sector` field).
2. For financials: EBIT = OPERATE_PROFIT directly (do not add back FINANCE_EXPENSE).
3. Add a `sector` parameter to the NOPAT calculation function.
4. For the MVP, if sector detection is unreliable, exclude financial stocks from ROIC analysis and set their Alpha component to neutral.

**Warning signs:**
- ICBC (601398.SH) NOPAT exceeds total profit.
- Financial companies consistently show top-decile ROIC-WACC spreads.
- NOPAT for a bank equals total profit + interest expense (the incorrect formula).

**Phase to address:**
Phase 1 (ROIC-WACC Engine) -- sector-aware NOPAT must be implemented before ROIC computation.

---

### Pitfall 4: Composite Alpha Score Collapses Because Components Are Not Normalized to the Same Scale

**What goes wrong:**
The Alpha score uses fixed weights: 40% ROIC-WACC, 30% Capital Allocation, 20% Policy Resonance, 10% Moat Trend. Each component produces values on different scales: ROIC-WACC spread is in percentage points (e.g., -5% to +15%), capital allocation is a 0-1 score, policy resonance is a similarity score (0.7-1.0), and moat trend is a 3-year slope (could be any value). Computing `0.4 * spread + 0.3 * capital + 0.2 * policy + 0.1 * moat` produces meaningless numbers because the raw values are not comparable. ROIC-WACC in percentage points dominates everything else.

**Why it happens:**
The existing system has no precedent for composite scoring. The `risk_service.py` computes individual metrics (M-Score, F-Score) and determines risk level via discrete thresholds, not weighted combination. The `yield_service.py` uses simple if/elif thresholds for recommendation. Neither normalizes continuous values to a standard scale.

**How to avoid:**
1. Normalize every component to a 0-1 scale before weighting (OECD Handbook on Constructing Composite Indicators methodology):
   - ROIC-WACC spread: use min-max normalization with historical CSI 300 bounds (e.g., -10% maps to 0, +20% maps to 1).
   - Capital allocation: already 0-1 if designed correctly (buyback yield percentile + dividend stability score + expansion penalty).
   - Policy resonance: map the classification output (DIRECTLY_BENEFITS=1.0, INDIRECTLY_BENEFITS=0.5, NOT_RELATED=0.0) -- do NOT use the raw cosine similarity score.
   - Moat trend: normalize the 3-year ROIC-WACC spread change using rank-based normalization (percentile within CSI 300 peer group).
2. After normalization, apply fixed weights: `alpha = 0.4 * roic_wacc_norm + 0.3 * cap_alloc_norm + 0.2 * policy_norm + 0.1 * moat_norm`.
3. When any component is unavailable (data quality issue, negative invested capital), substitute 0.5 (neutral) and track the substitution in the audit trail.
4. Store both raw values and normalized values in the database for reproducibility.

**Warning signs:**
- Alpha scores cluster in a narrow range (e.g., 0.01 to 0.03) because one component dominates with small absolute values.
- Alpha scores fall outside 0-1 range (indicates normalization failure).
- ROIC-WACC component contributes 95% of the Alpha score variance (indicates the spread scale overwhelms other components).

**Phase to address:**
Phase 4 (Composite Alpha Score) -- normalization must be defined before any weight is applied.

---

### Pitfall 5: Policy Resonance False Positives -- Semantic Matching Returns Irrelevant Policy Documents

**What goes wrong:**
The policy resonance engine uploads policy documents and matches them against stocks via the existing Qdrant vector store using bge-m3 embeddings. The critical failure mode is false positives: a policy about "new energy vehicle subsidies" matches a stock because the annual report mentions "new energy" in a risk factor discussion, not because the company benefits from the policy. The system then auto-adjusts the DCF terminal growth rate upward, producing an inflated intrinsic value. Additionally, DeepSeek LLM might hallucinate policy effects not supported by the matched text (e.g., suggesting a 5% terminal growth rate boost when the policy text mentions subsidies with no quantified impact).

**Why it happens:**
The existing `SemanticRetriever` uses a `score_threshold` of 0.7 (from `RAGConfig.SEARCH_SCORE_THRESHOLD`). This threshold was calibrated for matching annual report sections to financial queries, not for matching policy documents to company descriptions. Policy documents use broad language ("support strategic emerging industries") that matches many companies at high similarity scores. The retriever does not distinguish between "company benefits from policy" and "company mentions policy-related keywords."

**How to avoid:**
1. Raise the policy matching score threshold to 0.85 minimum. Policy matching requires higher precision than document retrieval.
2. Add a "policy relevance classification" step between retrieval and DCF adjustment: use the LLM (DeepSeek) to classify each match as `DIRECTLY_BENEFITS`, `INDIRECTLY_BENEFITS`, or `NOT_RELATED`. Only `DIRECTLY_BENEFITS` triggers DCF parameter adjustments.
3. Cap the DCF terminal growth rate adjustment from policy resonance to +/- 1 percentage point maximum.
4. Use a separate Qdrant collection for policy documents (e.g., `policy_documents`) with different chunking parameters and metadata schema (issuing_authority, effective_date, policy_category). Never mix document types in the same collection.
5. Constrain the LLM prompt: "If the policy text does not contain specific numerical targets or quantified impacts, return null adjustments." Always include matched text snippet in response for user verification.

**Warning signs:**
- Every CSI 300 stock shows "policy resonance" with the latest industrial policy document.
- DCF terminal growth rates all drift upward after uploading a supportive policy document.
- Policy matches cite risk factor sections of annual reports as "evidence" of policy alignment.
- The Alpha score distribution shifts dramatically (all stocks score higher) after policy document upload.

**Phase to address:**
Phase 3 (Policy Resonance Engine) -- the precision threshold and classification step must be built into the initial implementation.

---

### Pitfall 6: Buyback Data Is Fragmented and Incomplete for A-Share Stocks

**What goes wrong:**
The capital allocation scorecard requires buyback yield (shares repurchased / market cap). AKShare's `stock_repurchase_em()` returns ALL 5088 stocks' buyback data with no per-stock filtering option. It aggregates announcement data from East Money, not actual execution data. The `已回购金额` (actual repurchase amount) field is often empty or reflects cumulative amounts, not annual flow. Pre-2019 data is sparse because buybacks were restricted until the 2018 Companies Law revision.

**Why it happens:**
A-share buyback disclosure requirements changed in 2018-2019. Many companies announce buyback plans but execute slowly or not at all. The existing `akshare_client.py` has no buyback-related methods -- this is entirely new data fetching.

**How to avoid:**
1. Fetch `stock_repurchase_em()` once, cache the entire dataset in Redis with 1-hour TTL, filter in-memory by stock code. Do NOT call per-stock.
2. Use `已回购金额` (actual amount) only. Do NOT use `拟回购金额` (planned amount) as a proxy.
3. If actual data is unavailable for a stock, set buyback yield to 0.0 with a `data_quality` flag of `"INCOMPLETE"`.
4. Exclude buyback from the capital allocation score when data is unavailable and reweight the remaining components.
5. TREASURY_SHARES from the balance sheet is cumulative, not annual flow -- do not use it for buyback yield.

**Warning signs:**
- `stock_repurchase_em()` returns empty DataFrame for most CSI 300 stocks.
- Buyback yield is 0 for all stocks in the test set.
- Capital allocation scores cluster around a narrow range because buyback data is missing for 90% of stocks.

**Phase to address:**
Phase 2 (Capital Allocation Scorecard) -- buyback data quality must be assessed before the scorecard formula is finalized.

---

### Pitfall 7: Moat Trend Survivorship Bias -- Only Looking at Current CSI 300 Constituents

**What goes wrong:**
The moat trend requires 3 years of ROIC-WACC data. The CSI 300 index is reconstituted semi-annually. Stocks that deteriorate are removed and replaced. If the system only analyzes current CSI 300 constituents, it systematically overestimates moat persistence because the "losers" have been removed. A stock that was in CSI 300 in 2022 but dropped out in 2024 is invisible to the analysis.

**Why it happens:**
The PROJECT.md constrains the stock universe to "CSI 300 constituents only." The existing `get_index_constituents()` in `akshare_client.py` returns the CURRENT composition, not historical. If moat trend analysis fetches current CSI 300 stocks and looks back 3 years, survivorship bias is built into the data selection.

**How to avoid:**
1. For the MVP, acknowledge the bias explicitly in the API response metadata: `"moat_trend_data_note": "Based on current CSI 300 constituents only; excludes delisted/relegated stocks."`
2. Do NOT compute cross-sectional average moat trends and present them as "market averages."
3. Require minimum 3 years of data for moat trend. Stocks with less history get `data_insufficient` flag and moat component set to 0.5 (neutral).
4. Fetch historical CSI 300 compositions from AKShare if available, or use static snapshots.

**Warning signs:**
- Average moat trend across all CSI 300 stocks is strongly positive (should be near zero in efficient market).
- 0% of stocks show deteriorating moats.
- 3-year lookback fails for stocks that IPO'd less than 3 years ago.

**Phase to address:**
Phase 1 (ROIC-WACC Engine) -- the 3-year data requirement must be validated against the CSI 300 stock universe.

---

### Pitfall 8: NOPAT Includes Non-Recurring Items -- Distorted ROIC for Companies With Government Subsidies

**What goes wrong:**
Chinese listed companies frequently report large non-recurring items: government subsidies (classified under `营业外收入` or `其他收益`), asset impairment charges (`资产减值损失`), and gains/losses from disposal of assets. Using reported operating profit without adjustment inflates or deflates NOPAT unpredictably. A company receiving 2 billion yuan in subsidies shows high ROIC but the underlying business may be destroying value.

**Why it happens:**
AKShare's `stock_profit_sheet_by_report_em` returns raw financial statement line items. The existing `data_service.py` standardizes field names but does not separate recurring from non-recurring items because M-Score and F-Score did not need this distinction.

**How to avoid:**
1. Define NOPAT as: `Operating Profit (营业利润) - Income Tax on Operating Profit`, NOT as `Net Income + After-Tax Interest`. This avoids `营业外收支` entirely.
2. If using the net income approach: subtract `营业外收入`, add back `营业外支出`, subtract `资产减值损失`. Document each adjustment.
3. Store the NOPAT adjustment breakdown in the audit trail (follow `IndexAuditDetail` pattern from `risk_service.py:6-13`).

**Warning signs:**
- NOPAT differs from `Net Income + Interest x (1-T)` by more than 20% for any stock.
- Companies in subsidized industries (new energy, semiconductors) show consistently high ROIC.
- NOPAT adjustment fields are `None` or 0 for all stocks in the CSI 300 test set.

**Phase to address:**
Phase 1 (ROIC-WACC Engine) -- NOPAT definition must be finalized before computing ROIC.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reusing existing `calculate_wacc` (Ke only) for ROIC-WACC spread | No new function needed | Incorrect spread for leveraged companies | Never -- implement true WACC from the start |
| Using raw ROIC-WACC spread in Alpha score without normalization | Simpler code | ROIC-WACC dominates composite | Never -- normalization is essential |
| Hardcoding "blind expansion" threshold as CapEx growth > 30% when ROIC < WACC | Simple rule, easy to test | False positives for capex-heavy industries | MVP only -- make configurable per sector |
| Using cosine similarity directly as policy component | No LLM classification (saves cost/latency) | False positives inflate Alpha scores | Never -- LLM classification is essential |
| Computing buyback yield from planned (not executed) repurchases | More data, fewer nulls | Inflates capital allocation scores | Never -- only use actual execution data |
| Skipping 3-year lookback validation for moat trend | All stocks get a moat score | Recently IPO'd stocks have unreliable trends | MVP only -- flag insufficient history |
| Using TREASURY_SHARES from balance sheet as annual buyback amount | Field exists in AKShare | Cumulative value, not annual flow | Never |
| Duplicating WACC calculation instead of importing | Faster to implement | Two implementations diverge over time | Never -- single source of truth |

## Integration Gotchas

Common mistakes when connecting Alpha Engine features to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ROIC data from AKShare | Using column names directly without mapping to standardized fields | Add NOPAT components to existing field mapping in `data_service.py` |
| New ORM models (ROIC, Alpha) | Adding columns to existing tables | Create separate ORM models; FKs to stocks; new Alembic migrations |
| New config for ROIC/Alpha | Adding to `ValuationConfig` or `RiskConfig` | Create new `ROICConfig`/`AlphaConfig` frozen dataclass; add to `AppConfig` |
| Policy documents in Qdrant | Using `annual_reports` collection | Separate `policy_documents` collection with own metadata schema |
| Alpha score API | Single monolithic endpoint | Separate routes per component + composite endpoint reading cached sub-scores |
| Cache keys for ROIC data | Reusing `svf:v1:get_financial_report` keys | Bump to `svf:v2:get_roic_inputs:{ticker}:{year}` |
| WACC function | Copying into roic_service.py | Import from valuation_service; implement `calculate_true_wacc` alongside |
| CapEx from AKShare | Using raw `CONSTRUCT_LONG_ASSET` without sign normalization | Normalize CapEx to positive (absolute value), consistent with existing FCF pattern |
| Narrative for Alpha | 4 separate LLM calls for each component | Single comprehensive narrative; component breakdown as structured data |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Computing ROIC for all 300 stocks in single request | 30+ seconds; AKShare rate limiting | Pre-compute quarterly; cache; on-demand for individual stocks | 10+ concurrent requests |
| `stock_repurchase_em()` full-scan per stock | 5000+ rows per request; >2s | Fetch once, cache full dataset Redis 1h TTL; filter in-memory | Any multi-stock analysis |
| Policy document vectorization on upload | 2-5 minutes for large PDFs; timeout | Process async (existing document upload pattern) | Any document over 50 pages |
| Real-time Alpha score from scratch | 4 sub-computations across data sources | Cache sub-component scores; recompute from cache | 5+ Alpha requests/minute |
| AKShare field name changes | NOPAT uses wrong field silently | Pin AKShare version; validate columns before extraction | Every minor update |
| 3-year moat trend without index | Full table scan on financial_reports | Add composite index `(ticker, fiscal_year)` | 100+ stocks with trend data |

## Security Mistakes

Domain-specific security issues for Alpha Engine features.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Arbitrary policy document uploads | Malicious document boosting stocks via keyword matching | Validate source; limit upload rate; future: whitelist government domains |
| DCF auto-adjustment without audit trail | Terminal growth silently changes | Store original + adjusted params; include policy doc ID and match score |
| User-controllable normalization bounds | Target stock always scores highest | Hardcode bounds from historical CSI 300 data |
| Alpha score in recommendation language | Compliance violation ("BUY") | Use neutral language; include disclaimer |
| Policy resonance manipulation via multiple uploads | Inflating policy component | Deduplicate by content hash (SHA256); cap at 1.0 |

## UX Pitfalls

Common user experience mistakes when presenting Alpha Engine results.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Alpha score without component breakdown | Cannot understand why score is high/low | Show all 4 component scores alongside composite |
| ROIC-WACC spread without industry context | 3% spread meaningless without comparison | Show industry median spread |
| Auto-adjusted DCF without explanation | Unexpected intrinsic value | Show notification with policy name, confidence, adjustment amount |
| Moat trend from 1-2 years presented as reliable | Decisions on unreliable signals | Require 3 years; show "insufficient data" |
| `data_quality: INCOMPLETE` without explanation | Users confused why components are missing | Include human-readable explanation in response meta |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **ROIC Calculation:** Handles negative invested capital? Test: 600519.SH (Maotai), verify returns `None` not misleading negative %.
- [ ] **WACC for ROIC:** True WACC (not just Ke)? Test: leveraged vs unleveraged company show different WACC.
- [ ] **Financial Sector NOPAT:** Sector-aware formula? Test: ICBC (601398.SH) NOPAT < total_profit.
- [ ] **Buyback Data:** Actual execution (not planned)? Test: verify `已回购金额` populated; cross-reference Midea Group 2022.
- [ ] **Dividend Stability:** Handles stock splits? Test: stock with 10:1 split; verify adjusted DPU.
- [ ] **Policy Matching:** Relevant results only? Test: semiconductor policy + Maotai = no match.
- [ ] **Alpha Score:** Normalized [0,1]? Test: all CSI 300 stocks; verify reasonable distribution.
- [ ] **Blind Expansion:** No false positives for cyclicals? Test: utility with regular CapEx cycles.
- [ ] **Moat Trend:** Handles non-calculable ROIC years? Test: stock where Year 2 had negative invested capital.
- [ ] **nan Values:** Debt-free companies handled? Test: company with nan SHORT_LOAN/LONG_LOAN; verify no nan propagation.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Negative invested capital producing wrong ROIC | LOW | Add guard; recompute ROIC; update Alpha scores |
| True WACC not implemented (using Ke only) | HIGH | Implement true WACC; recompute ALL historical spreads, moat trends, Alpha |
| Financial sector NOPAT inflated | MEDIUM | Add sector detection; recompute NOPAT for financials; cascade |
| Alpha score not normalized | HIGH | Implement normalization; recompute all Alpha scores; update DB |
| Policy false positives inflating Alpha | MEDIUM | Raise threshold; add LLM classification; recompute policy + Alpha |
| Buyback data using planned not actual | MEDIUM | Switch to actual; recompute capital allocation + Alpha |
| Survivorship bias in moat trend | LOW (MVP) | Add disclaimer; plan historical CSI 300 composition |
| nan debt values breaking chain | LOW | Add nan-to-zero in extraction layer; recompute affected analyses |
| Duplicated WACC diverging | LOW | Refactor to import; recompute affected analyses |
| DCF auto-adjusted without audit trail | MEDIUM | Add audit fields; backfill from logs if available |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Negative invested capital | Phase 1: ROIC-WACC Engine | Compute ROIC for 600519.SH; verify None + non_calculable flag |
| True WACC vs Ke | Phase 1: ROIC-WACC Engine | Compute WACC for 000002.SZ (Vanke); verify differs from Ke |
| Financial sector NOPAT | Phase 1: ROIC-WACC Engine | Compute for ICBC; verify NOPAT < total_profit |
| NOPAT non-recurring items | Phase 1: ROIC-WACC Engine | Compare NOPAT with/without adjustments for 3 stocks |
| nan debt values | Phase 1: ROIC-WACC Engine | Test debt-free company; verify no nan propagation |
| Buyback data incompleteness | Phase 2: Capital Allocation | Fetch for 10 stocks; verify coverage and quality flags |
| Blind expansion false positives | Phase 2: Capital Allocation | Test utility with CapEx cycles |
| TREASURY_SHARES misuse | Phase 2: Capital Allocation | Verify annual flow, not cumulative treasury stock |
| Policy matching false positives | Phase 3: Policy Resonance | Semiconductor policy + Maotai = no match |
| DCF over-adjustment | Phase 3: Policy Resonance | Verify terminal growth adjusts max +/- 1pp |
| LLM hallucination in DCF adjustment | Phase 3: Policy Resonance | Verify constrained prompt; source text in response |
| Alpha score normalization | Phase 4: Composite Alpha | All CSI 300; verify distribution; all in [0,1] |
| Survivorship bias disclaimer | Phase 1: ROIC-WACC Engine | Verify API response includes data quality note |
| Cache key collision | Phase 1: ROIC-WACC Engine | Fetch via old and new keys; verify no collision |
| WACC duplication | Phase 1: ROIC-WACC Engine | grep for WACC outside valuation_service.py; verify import |

## Sources

- Codebase analysis: `valuation_service.py` (WACC = Ke only), `risk_service.py` (audit trail, safe ratio), `akshare_client.py` (data fetching, rate limiting), `config.py` (frozen dataclass pattern), `rag/retriever.py` (search threshold), `data_service.py` (field standardization), `models/valuation.py` (Pydantic patterns), `yield_service.py` (threshold patterns)
- PROJECT.md: Alpha Engine V2.0 requirements, constraints, key decisions, tech debt list
- AKShare: `stock_repurchase_em()` (full-scan API), `stock_profit_sheet_by_report_em` (nan for debt-free), `index_stock_cons_csindex` (current composition only)
- OECD Handbook on Constructing Composite Indicators (Nardo et al., 2008): normalization methodology, weight sensitivity
- Damodaran, A.: ROIC methodology for financial vs non-financial companies
- Chinese Accounting Standards (CAS): non-recurring items, government subsidies, asset impairment
- A-share buyback regulatory history: 2018 Companies Law revision; actual vs planned execution gap

---
*Pitfalls research for: Alpha Engine V2.0 (v1.2 milestone)*
*Researched: 2026-05-03*
