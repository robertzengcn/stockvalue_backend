# Pitfalls Research: Market Index Value Scanner (v1.5)

**Domain:** Batch market scanning added to an existing single-stock financial analysis platform (FastAPI + SQLAlchemy 2.0 + AKShare/efinance + Redis + arq worker)
**Researched:** 2026-06-04
**Confidence:** HIGH (codebase-verified -- inspected `akshare_client.py`, `valuation_service.py`, `cache.py`, `worker.py`, `config.py`, existing PRD and technical design docs)

---

## Critical Pitfalls

Mistakes that cause rewrites, incorrect financial results, or silent data corruption.

---

### Pitfall 1: AKShare Rate Limiting Cascades Into Batch Failure

**What goes wrong:**
AKShare scrapes East Money (dongfangcaifu) via HTTP. The existing `AKShareClient._run_sync` enforces a 0.5-second minimum interval between requests and retries up to 5 times with exponential backoff (2s, 4s, 8s, 16s, 30s). When scanning CSI 300 + CSI 500 = ~800 stocks, even a coarse screen needs at minimum one price lookup per stock. At 0.5s/request, that is 400 seconds (6.7 minutes) for prices alone. But the real danger is not time -- it is that East Money drops connections and blocks IPs after sustained rapid access. Once blocked, all retries fail, and the entire batch scan dies because the retry loop (lines 118-143 in `akshare_client.py`) exhausts all 5 attempts and raises `ExternalAPIError`.

In batch mode, this failure cascades: the first 50 stocks succeed, then East Money throttles, retries start consuming 2+30 seconds each, and by stock 200 the IP is blocked. The scan run ends in `failed` status with zero candidates, even though 200 stocks had usable data.

**Why it happens:**
The rate limiter in `_run_sync` is instance-scoped (`self._last_request_time`). It only enforces spacing between consecutive calls to the same `AKShareClient` instance. But `ExternalDataService` creates one client instance. In an async context with `asyncio.Semaphore(5)`, up to 5 coroutines can be waiting simultaneously. When the semaphore releases them, they all call `_run_sync` at nearly the same instant. The `time.monotonic()` check prevents true simultaneous requests, but the spacing becomes serial: request, sleep 0.5s, request, sleep 0.5s -- exactly the pattern East Money flags as automated scraping.

**How to avoid:**
1. Use a single shared `asyncio.Semaphore` or `asyncio.Lock` for ALL AKShare calls during a scan, not just the concurrency semaphore for deep analysis. Set the scan-wide request rate to 1 request per 1.0-1.5 seconds minimum, not 0.5s.
2. Batch-screening should prefer bulk APIs where available. For example, `stock_zh_a_spot_em()` returns ALL A-share real-time quotes in one call -- use this instead of calling `get_current_price` per stock.
3. Cache aggressively. The existing Redis cache has 5-minute TTL for prices and 24-hour TTL for financials. For a scan that takes 30 minutes, prices fetched at minute 1 are still valid at minute 30 (post-market). Ensure the scan service checks cache before making external calls.
4. Implement "partial success" explicitly: if the data source fails for stocks 201-800, save candidates from stocks 1-200, mark the run as `partial_failed`, and record which tickers failed in `error_summary`.
5. Add a circuit breaker: if 5 consecutive AKShare calls fail, pause the scan for 60 seconds, then retry. If still failing, mark run as `partial_failed` with the stocks already processed.

**Warning signs:**
- Scan run times that suddenly increase from 10 minutes to 30+ minutes (retry storms).
- `ExternalAPIError` in logs from `akshare_client.py` with "failed after 5 attempts".
- Scan runs consistently showing `total_count=800` but `screened_count=0`.
- `MarketScanRunRepository.mark_failed` called more often than `mark_completed`.

**Phase to address:**
Phase 3 (Scan Service) -- the request throttling and circuit breaker must be built into `MarketScannerService` from the start. Phase 1 tests should mock the external data source; Phase 3 tests should simulate throttling with mock delays.

---

### Pitfall 2: Value Traps Slip Through When Screening Uses Only Valuation Metrics

**What goes wrong:**
A stock screening for "low PE, low PB, high dividend yield" catches stocks that are cheap for good reason: deteriorating business fundamentals. A typical value trap in CSI 300/500: cyclical industrial company at PE=5, PB=0.6, 8% dividend yield -- looks like a steal. But revenue has declined 3 consecutive years, operating cash flow is negative, the dividend is funded by debt, and ROIC is below WACC. The scanner marks it as "undervalued with 50% safety margin" when in reality the intrinsic value is collapsing faster than the price.

The PRD correctly identifies this risk (Section 16.2) and the 3-layer funnel design is intended to prevent it. But the vulnerability is in the implementation: if the coarse screen (Layer 1) only filters by valuation multiples and the quality review (Layer 3) only runs on stocks that passed Layer 2, then fundamentally broken companies with temporarily low PE/PB still get DCF analysis and can appear as "undervalued" if DCF parameters default to positive growth rates.

**Why it happens:**
The default `DCFParams` in the existing codebase uses `growth_rate_stage1` and `growth_rate_stage2` that are positive values. If the scanner uses these defaults for all stocks, a company with shrinking revenue still gets projected FCF growth. The terminal value (which often represents 60-80% of total DCF value) amplifies this: a company with 2% terminal growth assumed will show a large intrinsic value even if the business is dying.

The existing `ValuationConfig` has `MIN_GROWTH_RATE_STAGE1: float = -0.50` (allowing negative growth), but nothing forces the scanner to use negative growth for declining companies. Without explicit logic that detects declining fundamentals and adjusts DCF parameters downward, the scanner defaults to optimistic assumptions.

**How to avoid:**
1. The coarse screen (Layer 1) MUST check operating cash flow positivity BEFORE any valuation screening. The technical design already includes `operating_cash_flow_positive` in `ScreeningSnapshot` -- enforce that it is a hard exclusion, not a soft signal.
2. In the quality review (Layer 3), require at minimum:
   - `risk_level != high` (existing M-Score and F-Score must pass)
   - `operating_cash_flow / net_income > 0.5` for at least the latest year (catches profit-cash divergence)
   - `revenue_decline_years < 3` consecutive (catches structural decline)
3. When DCF parameters are not stock-specific, the scanner should adjust `growth_rate_stage1` based on recent revenue trend: if 3-year revenue CAGR is negative, use that CAGR (clamped to `MIN_GROWTH_RATE_STAGE1`) instead of a default positive growth.
4. Add `value_trap_risk` as an explicit field in the candidate output: a composite of declining revenue, negative FCF trend, and high dividend payout ratio. Flag it as a `risk_flag` even if the stock passes all thresholds.

**Warning signs:**
- Candidates list dominated by cyclical industrials, resource companies, or real estate (sectors prone to value traps in China).
- Candidates showing negative 3-year revenue CAGR but positive projected FCF growth in audit trail.
- Candidate dividend yield above 8% with payout ratio above 90% (dividend not sustainable).
- `risk_level = medium` candidates with `margin_of_safety > 40%` (too good to be true).

**Phase to address:**
Phase 2 (Screening and Scoring Engine) -- the coarse screen exclusion rules must include fundamental quality filters, not just valuation filters. Phase 3 (Scan Service) -- the DCF parameter adjustment logic based on revenue trend.

---

### Pitfall 3: DCF Parameter Sensitivity Produces Unreliable Batch Results

**What goes wrong:**
DCF intrinsic value is extremely sensitive to three inputs: growth rate, WACC (discount rate), and terminal growth rate. A 1% change in terminal growth rate can swing intrinsic value by 20-40%. In batch mode, using the same default parameters for all 800 stocks creates systematic errors:
- Banks and insurance companies (financials) have fundamentally different cash flow structures -- DCF is inappropriate for them. Yet CSI 300 contains ~60 financial stocks.
- High-growth tech stocks in CSI 300 (e.g., BYD, CATL) need different growth rates than mature consumer staples (e.g., Maotai, Wuliangye).
- Cyclical stocks at trough earnings show artificially low PE/PB, making DCF projections from trough FCF misleadingly low or high depending on where in the cycle the base FCF is captured.

The existing `analyze_dcf_valuation` in `valuation_service.py` takes `DCFParams` as input but has no logic to validate whether those parameters make sense for the stock's sector or current position in the business cycle.

**Why it happens:**
The current system is designed for single-stock analysis where a human provides or reviews DCF parameters. Batch mode removes that human checkpoint. Developers naturally reach for a single default `DCFParams` object to use across all stocks because per-stock parameter tuning for 800 stocks defeats the purpose of automation.

The existing `ValuationConfig` has wide ranges (`MIN_GROWTH_RATE_STAGE1: -0.50` to `MAX_GROWTH_RATE_STAGE1: 1.0`) but no logic to select the right range for each stock. The scanner will either use a fixed middle value (producing mediocre results for all stocks) or attempt to auto-derive parameters from financial data (introducing its own class of errors).

**How to avoid:**
1. Do not rely solely on DCF for the "value confirmation" layer. Add a relative valuation check as a sanity gate: if DCF says undervalued but PE/PB percentile is in the top 50% of its 5-year range, flag the candidate with reduced confidence.
2. Segment stocks by sector before DCF. Use at minimum 3 parameter profiles: (a) financials -- skip DCF, use PB-based valuation instead; (b) high-growth -- use shorter stage 1 with higher growth; (c) mature/stable -- use standard 2-stage DCF.
3. Always run DCF sensitivity analysis in batch mode: compute intrinsic value at +/- 1% terminal growth and +/- 1% WACC. If the "undervalued" conclusion flips in any sensitivity scenario, reduce the composite score and add a `risk_flag: "DCF conclusion sensitive to parameter assumptions"`.
4. Record all DCF parameters in the `audit_trail` JSONB column so users and developers can diagnose why a stock appeared as a candidate.
5. The composite score should weight DCF-based `margin_of_safety` at 35% but NOT make it a sole gate. A stock with `margin_of_safety = 25%` (below the 30% threshold) but strong Alpha and low risk should still be visible to users -- just not labeled as "deep value."

**Warning signs:**
- Financial sector stocks (banks, insurance, securities) appearing as DCF-undervalued candidates.
- Same 10-15 stocks appearing as candidates every single scan day (systematic bias in parameters).
- Candidate list shows no sensitivity to market conditions (always same results regardless of price movement).
- Terminal value representing more than 80% of total intrinsic value in audit trail.

**Phase to address:**
Phase 2 (Screening and Scoring Engine) -- the scoring normalization and sensitivity flagging. Phase 3 (Scan Service) -- sector-based parameter profiles.

---

### Pitfall 4: Index Constituent Data Staleness and Adjustment Gaps

**What goes wrong:**
CSI 300 and CSI 500 undergo semi-annual rebalancing (June and December) with occasional quarterly interim adjustments. The scanner fetches constituents via `AKShareClient.get_index_constituents` (which calls `index_stock_cons_csindex`), but if the scanner runs before the CSI website updates its data (typically a 1-3 day lag after the effective date), the scanner uses stale constituents. Worse, if the scanner caches the constituent list and never re-fetches, it can scan stocks that were removed from the index months ago while missing newly added stocks.

A subtler variant: AKShare's `index_stock_cons_csindex` returns stock codes as integers when the data source does not zero-pad, causing `000001` to become `1`. The existing codebase already handles this in `eastmoney_hsf10_symbol` for individual lookups but the constituent list parser may not normalize codes, leading to failed data fetches for affected tickers during the scan.

**Why it happens:**
The PRD's FR-01 says "on sync failure, keep the previous constituent pool" (in Chinese: "同步失败时保留上一次可用成分股池"). This is correct resilience, but it means the scanner can silently operate on stale data. No one monitors whether the constituent list actually reflects the current index. The technical design's `deactivate_missing` repository method handles removals, but there is no alerting when the list does not update after a known rebalancing date.

**How to avoid:**
1. Store the effective date of each constituent list. If the latest effective date is more than 7 days old during a scan, log a warning. If it is more than 30 days old, fail the scan.
2. Know the CSI rebalancing schedule (second Friday of June and December). After those dates, force a constituent refresh before any scan runs.
3. Normalize all stock codes to 6-digit zero-padded strings immediately after fetching from AKShare. Apply `str.zfill(6)` at the AKShare client layer, not at the consumer layer.
4. Validate constituent count after each sync: CSI 300 must have exactly 300 active constituents, CSI 500 must have 500. If the count is off by more than 5, log a data quality warning.
5. Store the raw AKShare response in `source_raw` (JSONB) so that data quality issues can be diagnosed retroactively.

**Warning signs:**
- `index_constituents` table showing 295 or 310 active tickers for CSI 300.
- Stock codes like `1` or `600` appearing in the constituent list.
- Scan runs that analyze stocks not actually in the index.
- Constituent `effective_date` older than 60 days without any update.

**Phase to address:**
Phase 1 (Database and Domain Models) -- the constituent model must enforce code normalization and count validation. Phase 3 (Scan Service) -- the constituent refresh logic with rebalancing awareness.

---

### Pitfall 5: Scan Idempotency Failure Produces Duplicate Candidates

**What goes wrong:**
The technical design specifies that scan runs should be idempotent: "re-running the same run should not produce duplicate candidates" (in Chinese: "重复执行同一 run 不应产生重复候选"). But if the scanner creates the `market_scan_runs` record, processes stocks, creates `market_scan_candidates` records, and then the process crashes or is retried, it will create a new run and potentially duplicate candidates for the same stocks on the same scan date.

A more common scenario: the arq cron job fires `scan_market_indices` at 17:30 CST, but the previous day's scan is still running (slow data source). Two concurrent scans process overlapping stock lists, creating duplicate candidates in the database.

**Why it happens:**
The `market_scan_candidates` table has `UNIQUE(run_id, ticker)` but this prevents duplicates within a single run, not across runs on the same date. If two runs are created for the same scan date (e.g., one `daily_light` that was retried, or one automatic and one manual trigger), the same stock appears as a candidate in both runs. The API then returns duplicate entries when users query by date.

**How to avoid:**
1. Before creating a new scan run, check if a run with the same `scan_type` and `index_codes` is already `running` or `pending`. If so, skip the new run.
2. Use a Redis distributed lock per scan type (e.g., `lock:scan:daily_light:CSI300`) with a TTL of 60 minutes. The lock prevents concurrent scans of the same type.
3. Add a unique constraint on `(scan_type, index_codes, DATE(started_at))` to the `market_scan_runs` table (or a soft dedup check in the service layer).
4. In the API's candidate list endpoint, default to showing only the latest run's results unless the user explicitly requests historical runs.
5. The arq job should check for an existing `running` scan before starting a new one. If found, log and exit without error.

**Warning signs:**
- Multiple `market_scan_runs` records with `status=running` for the same `scan_type` on the same date.
- `market_scan_candidates` count for a given date exceeding the expected `candidate_count` of any single run.
- API returning duplicate tickers in candidate lists (same stock appearing twice for the same date).

**Phase to address:**
Phase 1 (Database and Domain Models) -- the unique constraints and run status tracking. Phase 3 (Scan Service) -- the distributed lock and dedup logic. Phase 4 (Worker and API) -- the arq job dedup check.

---

### Pitfall 6: Compliance -- Candidate List Reads as Investment Advice

**What goes wrong:**
The scanner outputs a ranked list of "undervalued stocks" with scores, safety margins, and text explaining why each is attractive. Despite the PRD's explicit statement that V1 does not provide buy/sell recommendations, the user experience of a ranked list with "comprehensive attractiveness score" and "structured reasons for inclusion" is functionally indistinguishable from investment advice in the eyes of Chinese regulators. If a user acts on a candidate and loses money, the "investment auxiliary tool" label does not protect against complaints or regulatory scrutiny.

The risk is amplified by the composite scoring system: a stock ranked #1 with a 90/100 composite score and "Safety margin 45%, ROIC-WACC positive, strong dividend yield" as reasons reads exactly like a "strong buy" recommendation, regardless of the disclaimer text.

**Why it happens:**
The PRD correctly identifies this risk (Section 16.5) and the technical design says "LLM only for expression, not calculation" (Section 16.3). But the compliance boundary is in the user-facing presentation, not in the backend calculation. The backend produces structured data that frontend developers will render as a recommendation list. Without explicit guardrails in the API contract (field names, descriptions, required disclaimers), the frontend will naturally present it as "top picks."

China's regulatory framework distinguishes between "investment advisory" (requires CSRC license) and "investment auxiliary tools" (information services). But CAC's algorithm registration requirement applies to any algorithmic recommendation system that "influences user decisions." A ranked stock list generated by a scoring algorithm almost certainly qualifies.

**How to avoid:**
1. API field names must use neutral terminology: `composite_score` is fine, but never use "recommendation" or "rating" in any field name. The `reasons` field should be called `selection_factors` or `inclusion_criteria`.
2. Every API response that returns candidates MUST include a mandatory `disclaimer` field with standardized text: "This is an automated screening tool for research purposes only. It does not constitute investment advice, buy/sell recommendations, or profit guarantees."
3. The `reasons` field should always include at least one `risk_flag` -- never show a candidate with only positive factors.
4. Do not rank candidates by "attractiveness" -- instead allow sorting by individual metrics (margin of safety, alpha score, risk level) and let the user decide what to prioritize.
5. The composite score documentation should explicitly state it is for "relative ordering within this scan batch" not an "absolute quality measure."
6. Add a `data_freshness_warning` field to candidates: "Data as of [date]. Market conditions may have changed."

**Warning signs:**
- API response contains words like "recommend," "buy," "strong," "signal" in any field.
- Candidate list presented without risk flags.
- Users asking "which stock should I buy?" in feedback channels.
- Composite score field documented as "investment quality score."

**Phase to address:**
Phase 2 (Screening and Scoring Engine) -- the scoring output model must enforce risk flag inclusion. Phase 4 (Worker and API) -- the API contract must include mandatory disclaimers. Every phase should have a compliance review checkpoint.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fixed DCF params for all stocks | Faster implementation, no parameter derivation logic | Systematically wrong valuations for 30-40% of candidates (financials, cyclicals, high-growth) | Never -- this produces misleading results that undermine user trust |
| Skip Layer 3 quality review for daily_light scan | Faster daily scans (30 min vs 60 min) | Value traps appear as candidates daily, users lose trust after acting on false positives | Never -- quality review is the entire point of the 3-layer funnel |
| Cache constituent list indefinitely (fetch once) | Eliminates one external API call per scan | Stale constituents after index rebalancing, wrong stocks scanned | Only acceptable with a max staleness cap (7 days) and rebalancing-date forced refresh |
| Store only candidate scores, not input snapshots | Simpler schema, less storage | Cannot explain why a candidate appeared historically; cannot reproduce results; audit trail gap | Never -- the technical design correctly requires `screening_snapshot` and `audit_trail` |
| Use a single SELECT * for all candidate queries | Simpler repository code | API latency degrades as candidates accumulate (millions of rows after months of daily scans) | Only with proper indexing and date-range filtering |
| Hardcode CSI index codes ("000300", "000905") | No configuration lookup needed | Cannot extend to new indices without code changes | MVP only -- the config design should already support configurable index codes |

## Integration Gotchas

Common mistakes when connecting to external services and existing internal services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AKShare batch pricing | Calling `get_current_price` per stock (800 calls) | Use `stock_zh_a_spot_em()` for bulk quote fetch (1 call returns all A-shares) |
| AKShare financial statements | Fetching full multi-year financials for all 800 stocks | Only fetch deep financials for stocks that pass Layer 1 coarse screen (typically 50-100 stocks) |
| Existing `ExternalDataService` cache | Assuming cache covers batch needs | Pre-warm cache for index constituents; verify cache hit rate is above 80% for financial data |
| Existing `RiskAnalyzer` | Passing raw AKShare data without field normalization | Reuse the same field extraction functions already in `data_service.py` (e.g., `_extract_akshare_revenue`) |
| Existing `DCFValuationService` | Calling full DCF with default params for every stock | First check `ValuationRepository.get_latest_for_ticker`; only recompute if result is stale (>30 days) |
| Existing `AlphaScoreRepository` | Computing Alpha for all 800 stocks in daily scan | Daily scan uses cached Alpha; only weekly deep scan recomputes Alpha for Top N |
| arq worker | Adding scan jobs without checking existing worker health | Check `ctx["market_scanner"]` exists; check no scan of same type is already running |
| PostgreSQL | Creating candidates without proper indexing on `(run_id, rank)` | Add indexes from day one; queries by run_id + rank are the hot path |
| Redis cache | Using the same cache key for scan data as for single-stock data | Use a separate cache key prefix (e.g., `scanner:`) to avoid collision and allow independent invalidation |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential external API calls per stock | Daily scan takes 60+ minutes instead of 30 | Bulk APIs for Layer 1, concurrency with semaphore for Layer 2/3 | CSI 300 alone is fine; CSI 300 + CSI 500 (800 stocks) exposes it |
| Unbounded candidate result set | API returns 200+ candidates, frontend hangs | Hard cap on candidates per run (e.g., 50); proper pagination | Any scan batch > 100 stocks passing Layer 1 |
| Full-table scan on market_scan_candidates | Candidate query takes 5+ seconds | Index on `(run_id, rank)`, index on `(ticker, calculated_at)` | After 30 days of daily scans (~15,000 candidate rows) |
| Redis cache stampede on scan start | All 800 stocks miss cache simultaneously, hammering AKShare | Pre-warm prices before scan starts; use `stock_zh_a_spot_em` bulk API | First scan of the day (cache cold after overnight TTL expiry) |
| Growing JSONB columns (audit_trail, screening_snapshot) | Candidate detail queries slow; storage bloats | Compress large JSONB fields; archive old runs after 90 days | After 90 days of daily scans (JSONB avg 5KB x 50 candidates x 90 runs = 22MB just in JSONB) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Manual scan trigger without authorization check | Any user can trigger expensive batch scans, running up API costs or triggering AKShare bans | Require admin role for `POST /api/v1/market-scanner/runs`; rate-limit even for admins |
| Exposing raw AKShare error messages in API responses | Internal infrastructure details (IP addresses, retry counts, East Money URLs) leak to users | Sanitize all error messages in API responses; log full errors server-side only |
| Candidate watchlist endpoint without ownership check | User A adds User B's watchlist entry | Verify `candidate_id` exists, extract ticker, call existing `WatchlistRepository.add` with current user context |
| No rate limiting on candidate list API | Scrapers can enumerate all scan results and reconstruct the screening model | Standard per-user rate limiting on all market-scanner endpoints |

## UX Pitfalls

Common user experience mistakes in financial screening tools.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing raw composite score without context | Users treat 85/100 as "strong buy signal" | Show score only relative to the batch: "Ranked #3 out of 42 candidates in this scan" |
| Candidate list changes daily with no explanation | Users confused why yesterday's top pick disappeared today | Track candidate appearance/disappearance between consecutive runs; show "New," "Removed," and "Persisted" badges |
| No indication of data quality | User trusts analysis that used stale or missing financial data | Show data completeness indicator: "Analysis based on 8/10 required metrics" |
| Only showing current scan results | Users cannot evaluate if the scanner is improving over time | Provide historical accuracy: "Last month's top 10 candidates had average +5% return vs CSI 300" (educational, not promotional) |
| Risk flags buried at the bottom | Users only see the positive reasons, miss the risks | Show risk flags with equal visual weight as inclusion reasons; at minimum one risk flag per candidate |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Constituent sync:** Fetches CSI 300 list -- but does it handle zero-padding, duplicate removal, and count validation? Verify with a real AKShare call.
- [ ] **Coarse screen:** Filters ST and suspended stocks -- but does it also filter stocks with missing PE/PB/dividend data? Missing data is different from "data not fetched."
- [ ] **DCF reuse:** Calls existing valuation service -- but does it check for stale results first? A valuation from 6 months ago with different prices is misleading.
- [ ] **Composite score:** Computes weighted sum -- but does it handle `None` values for components (missing Alpha, missing yield gap)? Score must degrade gracefully, not crash.
- [ ] **Scan idempotency:** Creates unique run_id -- but does it prevent concurrent scans? Two arq workers could pick up the same cron job.
- [ ] **Candidate reasons:** Generates structured text -- but does it always include at least one risk flag? All-positive candidates are compliance risk.
- [ ] **API pagination:** Supports page/limit -- but does it have a default limit (e.g., 50) and max limit (e.g., 200)? Unbounded queries are a DoS vector.
- [ ] **Error summary:** Records per-stock failures -- but does the run-level `error_summary` include counts by failure type (data_source, calculation, timeout)?
- [ ] **Audit trail:** Records DCF parameters -- but does it also record which data source was used (AKShare vs efinance vs Tushare vs cache)?
- [ ] **Worker cron:** Schedules run at 17:30 CST -- but is that UTC or CST in the arq cron config? arq cron uses UTC by default.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| AKShare IP blocked during scan | LOW | Mark run as `partial_failed`; wait 1-2 hours for block to clear; re-run with `scan_type=event_triggered` for failed tickers only |
| Value traps appearing as candidates | MEDIUM | Add post-hoc filter: scan past candidates for stocks that dropped >20% in 3 months after appearing; use pattern to adjust screening rules |
| Stale constituent list used for scan | LOW | Re-sync constituents; re-run scan. Previous candidates remain valid for their run_id (historical record). New run produces corrected results. |
| Duplicate runs on same date | LOW | Delete the duplicate run and its candidates (cascade); keep the one with more processed stocks |
| Wrong DCF parameters produced misleading candidates | MEDIUM | Update `rules_version` in `market_scan_rules`; re-run scan. Old candidates retain their `rules_version` for auditability. |
| Compliance issue in API response format | HIGH | API changes require frontend coordination. Add `disclaimer` field as mandatory; version the API (`/api/v2/market-scanner/`) if field names change |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| AKShare rate limiting | Phase 3 (Scan Service) | Test with mock that simulates rate limiting; verify run completes as `partial_failed` instead of `failed` |
| Value traps | Phase 2 (Screening and Scoring) | Unit test: stock with declining revenue + negative cash flow + low PE must be excluded by coarse screen or quality review |
| DCF parameter sensitivity | Phase 2 (Screening and Scoring) | Unit test: financial sector stock must not use standard DCF params; sensitivity flag must appear when conclusion flips at +/- 1% |
| Constituent staleness | Phase 1 (Database and Models) | Integration test: sync constituents, verify count matches expected (300/500), verify zero-padding |
| Scan idempotency | Phase 1 + Phase 3 + Phase 4 | Integration test: start scan, attempt second scan, verify second is skipped; test crash mid-scan, verify retry does not duplicate candidates |
| Compliance | Phase 2 + Phase 4 | Code review: every API response model includes `disclaimer`; every candidate has at least one `risk_flag`; no "buy" / "recommend" / "signal" language |

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| Phase 1 (Database and Models) | Forgetting to add indexes on `market_scan_candidates` from the start | Include `(run_id, rank)`, `(ticker, calculated_at)`, `(composite_score)` indexes in the initial migration |
| Phase 2 (Screening and Scoring) | Hardcoding thresholds into pure functions instead of making them configurable via `MarketScannerConfig` | Every threshold must come from config; no magic numbers in screening or scoring logic |
| Phase 3 (Scan Service) | Calling existing services synchronously without timeout protection | Wrap each stock's deep analysis in `asyncio.wait_for` with a configurable timeout (e.g., 60 seconds per stock) |
| Phase 3 (Scan Service) | Not handling the case where `ExternalDataService` returns `None` for financial data | Every external data call must check for `None` before passing to analysis services |
| Phase 4 (Worker and API) | arq cron timezone confusion (UTC vs CST) | Write explicit test: verify scan fires at 09:30 UTC (17:30 CST), not 17:30 UTC |
| Phase 4 (Worker and API) | Manual scan trigger blocking the API response | `POST /api/v1/market-scanner/runs` must only enqueue the arq job and return immediately; never run scan synchronously |

## Sources

- Codebase inspection: `akshare_client.py` (rate limiter at lines 108-113, retry at lines 115-143), `valuation_service.py` (DCF params sensitivity at lines 185-290), `config.py` (valuation thresholds), `cache.py` (TTL settings), `worker.py` (arq cron patterns)
- PRD: `doc/market_index_value_scanner_prd.md` (Sections 6, 11, 16)
- Technical Design: `doc/market_index_value_scanner_technical_design.md` (Sections 7, 9, 16)
- AKShare documentation: `index_stock_cons_csindex` function behavior (code normalization, count validation)
- CSI Index rebalancing schedule: semi-annual (June, December), announced by CSI Index Company
- China regulatory framework: CAC algorithm registration requirements; CSRC investment advisory vs auxiliary tool distinction
- DCF sensitivity analysis: standard financial modeling practice -- terminal value typically 60-80% of total enterprise value
- Piotroski F-Score design: specifically created to filter value traps from low PB screens (referenced in existing `risk_service.py`)

---
*Pitfalls research for: Market Index Value Scanner (v1.5)*
*Researched: 2026-06-04*
