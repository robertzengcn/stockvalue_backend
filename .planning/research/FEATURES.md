# Feature Research

**Domain:** Event-driven financial report monitoring and processing pipeline for A-share value investing analysis
**Researched:** 2026-05-01
**Confidence:** HIGH (based on existing codebase analysis, AKShare documentation, arq/APScheduler docs, and domain expertise)
**Scope:** v1.1 milestone ONLY -- new pipeline features; existing features (risk/valuation/yield analysis, RAG upload, caching) are assumed operational

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features any automated financial report pipeline must provide. Missing these means the system cannot reliably stay current with new disclosures, making the analysis engine stale and untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Disclosure schedule tracking | Users need the system to know when reports are due; AKShare provides `stock_report_disclosure` with appointment dates, change dates, and actual disclosure dates | LOW | AKShare `stock_report_disclosure(market, period)` returns scheduled + actual disclosure dates for all stocks. Data is per-period (e.g. "2025年报"), not continuous. Polling frequency: weekly during off-season, daily during reporting season (Jan-Apr). |
| New report detection (Smart Watcher) | The pipeline must automatically discover when new annual/quarterly reports appear without manual triggering | MEDIUM | Two complementary approaches: (1) scheduled polling of `stock_report_disclosure` comparing actual disclosure dates against last-processed timestamps, (2) polling `stock_yysj_em` (Eastmoney) as cross-check. Cannot use push/webhook because neither CNInfo nor Eastmoney offers one. |
| PDF download from disclosure source | Once a new report is detected, the system must download the actual PDF for parsing and RAG ingestion | MEDIUM | CNInfo provides downloadable PDF URLs via its announcement query interface. AKShare does not expose a direct download function; must use httpx to fetch PDF from CNInfo URLs. Need proper headers (User-Agent, Referer) and rate limiting (0.5s between requests minimum). |
| Structured state machine (PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE / FAILED) | Users and operators must be able to track processing progress and diagnose failures; without a state machine, tasks disappear into a black box | MEDIUM | States: PENDING (detected), DOWNLOADING (fetching PDF), PARSING (extracting text/tables), ANALYZING (running M-Score/F-Score/DCF), DONE (all complete), FAILED (with retry count and error detail). Each state transition must be atomic and persisted. Idempotent transitions (re-processing same state is a no-op). |
| Deduplication (source ID + SHA256 + business key) | The same report can appear in multiple data sources or polling cycles; processing the same report twice wastes resources and creates inconsistent analysis | MEDIUM | Three-tier dedup: (1) source announcement ID from CNInfo as primary key, (2) SHA256 hash of downloaded PDF bytes to detect identical content from different sources, (3) business key = ticker + fiscal_year + report_type for semantic dedup. Store processed report fingerprints in PostgreSQL for lookup. |
| Retry with exponential backoff for failed tasks | Network failures, rate limiting, and temporary data source outages are expected; the pipeline must recover gracefully without operator intervention | LOW | arq provides built-in `max_tries` and retry behavior. For APScheduler-triggered jobs, wrap in try/except with state transition to FAILED and schedule retry. Maximum 3 retries with exponential backoff (2s, 8s, 30s). Mark as permanently failed after max retries and log for manual intervention. |
| Status query API endpoint | Users and operators need to check pipeline status: how many reports pending, processing, done, failed; when was the last successful run | LOW | `GET /api/v1/pipeline/status` returns aggregate counts by state, last poll time, next scheduled poll time. `GET /api/v1/pipeline/tasks` returns paginated task list with filtering by state, ticker, date range. |
| Integration with existing RAG pipeline | Downloaded reports must be automatically chunked, embedded, and stored in Qdrant for semantic retrieval | LOW | Existing `DocumentService.process_upload()` handles PDF -> chunks -> embeddings -> Qdrant. Pipeline reuses this by calling `process_upload()` with downloaded PDF bytes. The only new code is wiring the pipeline to trigger DocumentService after successful download. |
| Integration with existing analysis services | When a new financial report arrives, risk/valuation/yield analysis should run automatically so the data stays fresh | MEDIUM | Existing `RiskAnalyzer`, `DCFValuationService`, `YieldAnalyzer` are pure functions that accept financial data. Pipeline triggers them sequentially after PDF parsing. Results persisted via existing repositories. Must handle partial failures (e.g., risk succeeds but DCF fails due to missing data). |

### Differentiators (Competitive Advantage)

Features that set this pipeline apart. No Chinese retail investor tool offers automated, end-to-end financial report ingestion with AI analysis.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Configurable CSI 300 watchlist with per-stock polling | Users can configure which stocks to monitor (default: CSI 300 constituents); avoids wasting resources on irrelevant stocks | LOW | Store watchlist in PostgreSQL (ticker list with metadata). AKShare provides CSI 300 constituent list via `index_stock_cons()`. Default: all CSI 300. User can add/remove via API. Polling checks only watchlist stocks. |
| Reporting season awareness (adaptive polling frequency) | During Jan-Apr annual report season, polling frequency increases automatically; during off-season, reduces to save resources and avoid rate limiting | MEDIUM | Polling adapts based on current date and `stock_report_disclosure` data. High season (Jan 1 - Apr 30): poll daily. Low season (May - Dec): poll weekly. Configurable via PipelineConfig frozen dataclass. Prevents unnecessary API calls while ensuring timely detection during peak disclosure periods. |
| Summary vs full-text report handling | Annual reports can be 200+ pages; many stocks also file a summary version. Pipeline should detect report type and handle appropriately (full report for RAG, summary for quick screening) | MEDIUM | CNInfo titles typically include "年度报告" (full) vs "年度报告摘要" (summary). Parse title from announcement metadata. Full reports: process through full RAG pipeline (PDF -> chunks -> embeddings -> Qdrant) + trigger full analysis. Summary reports: extract key metrics only, skip RAG ingestion. Both get deduplication. |
| Analysis completion notification via SSE | Frontend (future) or monitoring tools need real-time awareness when pipeline finishes processing a report, without polling the status endpoint repeatedly | MEDIUM | FastAPI `StreamingResponse` with `text/event-stream` content type. `GET /api/v1/pipeline/events` opens SSE connection. Server pushes events: `task_created`, `task_completed`, `task_failed`. Uses asyncio.Queue per connection. Events dispatched from state machine transitions. Client reconnects on disconnect. |
| Processing audit trail per report | Every step (detection, download, parse, analyze) logged with timestamps, durations, and error details; enables debugging and compliance | LOW | Extend existing `metadata_` JSONB field on documents table with pipeline audit entries. Each state transition appends `{state, timestamp, duration_ms, error}`. Aligns with existing frozen Pydantic audit trail pattern used in M-Score. |
| Concurrent pipeline processing with arq workers | Multiple reports can be processed simultaneously (download + parse + analyze for different stocks in parallel), rather than one-at-a-time sequential | MEDIUM | arq provides async job queue with configurable `max_concurrent_tasks`. Each report detection enqueues a job. Workers pick up jobs concurrently. Key constraint: no two jobs should process the same ticker simultaneously (use arq's `_job_id` parameter with ticker-based ID for uniqueness). |
| Subprocess-based calculation sandbox | Financial calculations (M-Score, DCF) execute in isolated subprocess with resource limits, not in the main process | MEDIUM | Uses `subprocess.run()` with timeout and memory limits. Current `calculation_sandbox.py` is a stub. Implementation: generate Python script with calculation inputs, execute in subprocess, parse JSON output. Provides isolation without Docker overhead. Sufficient for MVP. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|----------|---------------|-----------------|-------------|
| Real-time webhook push from CNInfo/Eastmoney | Zero-latency report detection sounds ideal | Neither CNInfo nor Eastmoney provides webhooks or push APIs for new announcements; building this would require reverse-engineering their infrastructure, which is fragile and potentially illegal | Polling with adaptive frequency (daily in season, weekly off-season); acceptable latency since value investors do not need sub-second report access |
| Playwright/Selenium browser automation for report discovery | Seems like a reliable way to scrape CNInfo | Browser automation is brittle (breaks on UI changes), resource-heavy (headless browser per request), and slow. CNInfo has documented HTTP APIs that return JSON -- no rendering needed | Use httpx to call CNInfo announcement query API directly; returns structured JSON with PDF download URLs. Simpler, faster, testable. |
| OCR processing for all scanned documents | Some older annual reports are scanned images without text layers | PaddleOCR is heavy (300MB+ model), slow (seconds per page), and the vast majority of CSI 300 annual reports from 2020+ have proper text layers | PyMuPDF text extraction first; if page yields <50 characters of text, flag for OCR fallback but do not implement OCR yet. Log the gap for future phase. |
| Celery + RabbitMQ for task queue | Industry-standard task queue, proven at scale | Massive operational overhead for current task volume (at most ~300 reports per quarter, ~10 per day during peak season). Requires RabbitMQ broker as additional infrastructure. arq + Redis is already in the stack and sufficient. | arq with Redis (already deployed for caching); handles current volume easily; asyncio-native, integrates with FastAPI lifecycle. |
| Processing all 5000+ A-share stocks | More coverage seems better | Data source rate limits (AKShare/CNInfo throttle aggressive usage), storage costs, and processing time explosion. CSI 300 is the stated MVP scope. | CSI 300 constituents only; configurable watchlist for future expansion. Pipeline designed to be extensible but scoped for validation. |
| Docker-based calculation sandbox | Maximum isolation for untrusted code execution | Adds Docker daemon dependency, container startup latency (seconds per calculation), and operational complexity. For MVP, subprocess isolation is sufficient since we control all calculation code (no user-submitted code). | Subprocess with timeout and memory limits via `resource` module. Re-evaluate Docker sandbox only if user-submitted scripts are added in v2+. |
| WebSocket for pipeline status | Bidirectional real-time communication | SSE is simpler, uses standard HTTP, works through proxies, and is sufficient for one-directional status push. WebSocket adds complexity (connection management, protocol handling, proxy compatibility) with no benefit for push-only use case. | SSE (Server-Sent Events) for status notifications. Single direction (server -> client) is all that is needed. |
| Storing full PDF binary in database | Convenient single-source-of-truth storage | PDFs are 2-20MB each; 300 stocks x 4 reports/year = ~2.4GB/year in PostgreSQL. Bloated database, slow backups, poor query performance on document tables. | Store PDFs on local filesystem (existing `UPLOAD_DIR` pattern), store file path in database. Database holds metadata only. |
| Processing reports from multiple markets simultaneously (A-share + HK) | Broader coverage from day one | HKEX has completely different APIs, disclosure schedules (different fiscal year patterns), and language (often bilingual). Doubles implementation complexity without doubling validation value. | A-share first (CNInfo + AKShare). HK support deferred to future milestone. Pipeline architecture designed to be market-agnostic via abstract watcher interface. |

---

## Feature Dependencies

```
[Smart Watcher (Disclosure Monitoring)]
    +--requires--> [AKShare stock_report_disclosure API] (EXTERNAL - confirmed available)
    +--requires--> [APScheduler / arq cron for periodic polling] (NEW)
    +--requires--> [PipelineConfig with season-aware schedule] (NEW)
    +--produces--> [List of newly disclosed reports]

[Report Deduplication]
    +--requires--> [PostgreSQL pipeline_tasks table] (NEW - migration needed)
    +--requires--> [Source announcement ID extraction from CNInfo] (NEW)
    +--requires--> [SHA256 hashing of PDF bytes] (NEW - stdlib hashlib)
    +--enhances--> [Smart Watcher] (prevents re-processing)

[PDF Download]
    +--requires--> [httpx client with rate limiting] (EXISTS in project deps)
    +--requires--> [CNInfo announcement URL construction] (NEW)
    +--requires--> [Local filesystem storage (UPLOAD_DIR)] (EXISTS)
    +--requires--> [Report Deduplication] (skip download if already processed)

[Report Parsing + Structuring]
    +--requires--> [PyMuPDF text extraction] (EXISTS in pdf_processor.py)
    +--requires--> [Title-based report type detection (full vs summary)] (NEW)
    +--enhances--> [RAG Pipeline] (chunks fed to existing DocumentService)

[State Machine]
    +--requires--> [PostgreSQL task state persistence] (NEW - migration)
    +--requires--> [Atomic state transitions with updated_at] (NEW)
    +--enhances--> [Status API] (queryable task states)
    +--enhances--> [SSE Notification] (events emitted on transitions)

[Analysis Triggering]
    +--requires--> [Existing RiskAnalyzer] (EXISTS)
    +--requires--> [Existing DCFValuationService] (EXISTS)
    +--requires--> [Existing YieldAnalyzer] (EXISTS)
    +--requires--> [ExternalDataService for fresh financial data] (EXISTS)
    +--requires--> [State Machine DONE state only after all analyses complete] (NEW)
    +--enhances--> [RAG Pipeline] (analyzed reports available for retrieval)

[RAG Integration]
    +--requires--> [Existing DocumentService.process_upload()] (EXISTS)
    +--requires--> [Existing QdrantVectorStore] (EXISTS)
    +--requires--> [Existing BGEEmbeddingClient] (EXISTS)
    +--independent--> Can work standalone (manual upload still works)

[SSE Notification]
    +--requires--> [State Machine] (events on transitions)
    +--requires--> [FastAPI StreamingResponse] (built-in)
    +--independent--> Optional; pipeline works without notifications

[Subprocess Sandbox]
    +--requires--> [subprocess.run with timeout/memory limits] (stdlib)
    +--requires--> [JSON-based input/output contract] (NEW)
    +--enhances--> [Analysis Triggering] (isolated calculation execution)
    +--independent--> Can ship without pipeline (enhances existing analysis)

[Status API]
    +--requires--> [State Machine] (queryable task states)
    +--requires--> [PostgreSQL aggregation queries] (NEW)
    +--independent--> Read-only; does not affect pipeline processing
```

### Dependency Notes

- **Smart Watcher is the pipeline entry point**: Everything else is downstream. Without automated detection, the pipeline degrades to manual upload (which already works). The watcher must be reliable and season-aware.
- **Deduplication gates PDF download**: Before downloading, the system checks whether this announcement ID / SHA256 / business key already exists. This prevents both duplicate downloads and duplicate analysis runs.
- **State machine is the backbone**: Every other feature (status API, SSE notifications, retry logic) depends on the state machine for source of truth. It must be persisted in PostgreSQL, not in-memory.
- **RAG integration reuses existing DocumentService**: No new RAG code needed. The pipeline calls `DocumentService.process_upload()` with downloaded PDF bytes. The existing parent-child chunking, bge-m3 embedding, and Qdrant upsert flow handles everything.
- **Analysis triggering reuses existing pure-function services**: RiskAnalyzer, DCFValuationService, and YieldAnalyzer are stateless. The pipeline fetches fresh financial data via ExternalDataService, then calls each analyzer. Partial failure handling: if one analyzer fails, mark the overall task state but record which analyses succeeded.
- **arq and APScheduler serve different roles**: APScheduler triggers the periodic Smart Watcher poll (cron-like scheduling). arq handles individual report processing jobs (async task queue with concurrency control, retry, and dedup). This separation keeps scheduling concerns separate from processing concerns.
- **Subprocess sandbox is independent**: It enhances calculation safety but the pipeline works without it (calculations run in-process as they do today). Ship it as an enhancement within the pipeline milestone, not a blocker.

---

## MVP Definition

### Launch With (v1.1 Pipeline)

The minimum needed to validate automated financial report ingestion and analysis.

- [ ] **Pipeline config (PipelineConfig frozen dataclass)** -- Polling schedule, rate limits, retry policy, watchlist scope. Extends existing config.py pattern.
- [ ] **PostgreSQL pipeline_tasks table (Alembic migration)** -- Task ID, ticker, source_announcement_id, SHA256, business_key, state, retry_count, error_detail, timestamps. New table alongside existing documents table.
- [ ] **Smart Watcher with season-aware polling** -- APScheduler cron job that calls AKShare `stock_report_disclosure`, detects new disclosures, deduplicates against pipeline_tasks, enqueues download jobs via arq.
- [ ] **PDF download client** -- httpx-based client for CNInfo PDF URLs with rate limiting (0.5s between requests), proper headers, filesystem storage.
- [ ] **State machine with atomic transitions** -- PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE / FAILED. Each transition persisted to pipeline_tasks. Idempotent re-processing.
- [ ] **Deduplication (announcement ID + SHA256 + business key)** -- Three-tier check before any processing begins. Prevents duplicate work across polling cycles and data sources.
- [ ] **arq worker for report processing jobs** -- Async job queue with Redis backend. `max_concurrent_tasks` configurable. Job uniqueness via `_job_id` (ticker-based).
- [ ] **RAG integration (reuse existing DocumentService)** -- Wire pipeline to call `DocumentService.process_upload()` after successful download. Zero new RAG code.
- [ ] **Analysis triggering (reuse existing services)** -- After RAG ingestion, trigger RiskAnalyzer + DCFValuationService + YieldAnalyzer with fresh data. Persist results via existing repositories.
- [ ] **Status API (GET /api/v1/pipeline/status, GET /api/v1/pipeline/tasks)** -- Read-only endpoints for pipeline monitoring.
- [ ] **Retry with exponential backoff** -- Failed tasks retry up to 3 times with increasing delays. Permanently failed tasks logged for manual review.
- [ ] **Comprehensive test suite (80%+ coverage)** -- Unit tests for each pipeline component (watcher, downloader, state machine, dedup). Integration test with mocked AKShare/Qdrant. E2E test with PostgreSQL test container.

### Add After Validation (v1.x)

- [ ] **SSE notification endpoint** -- Real-time push when tasks complete or fail. Requires state machine event emission. Add after core pipeline is stable.
- [ ] **Subprocess calculation sandbox** -- Isolated Python execution for financial calculations. Enhances safety but not required for pipeline to function.
- [ ] **Summary vs full-text report differentiation** -- Parse CNInfo announcement titles to detect report type; route full reports through RAG, extract key metrics from summaries only.
- [ ] **Configurable CSI 300 watchlist management API** -- CRUD endpoints for adding/removing stocks from the monitoring list. Default: all CSI 300.
- [ ] **Processing audit trail per report** -- Detailed step-by-step log with timestamps and durations in document metadata.

### Future Consideration (v2+)

- [ ] **HKEX monitoring** -- Hong Kong stock disclosure monitoring with different API, schedule, and language handling.
- [ ] **OCR fallback for scanned documents** -- PaddleOCR integration for PDFs without text layers. Triggered when PyMuPDF yields <50 chars per page.
- [ ] **Multi-market watcher abstraction** -- Abstract watcher interface allowing A-share, HK, and future market implementations behind a common interface.
- [ ] **Webhook notification to external systems** -- Push notifications to DingTalk, WeChat, or custom webhooks when high-priority reports are processed (e.g., fraud flags detected).
- [ ] **Incremental RAG updates** -- Instead of re-processing entire report, detect changes and update only affected chunks in Qdrant.
- [ ] **Batch CSI 300 screening automation** -- Scheduled full-universe screening using pipeline data; generates comparative reports across all constituents.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Pipeline config + DB migration | HIGH (foundation) | LOW | P1 |
| Smart Watcher (season-aware polling) | HIGH | MEDIUM | P1 |
| Deduplication (3-tier) | HIGH | MEDIUM | P1 |
| PDF download client | HIGH | MEDIUM | P1 |
| State machine (atomic transitions) | HIGH | MEDIUM | P1 |
| arq worker integration | HIGH | MEDIUM | P1 |
| RAG integration (reuse existing) | HIGH | LOW | P1 |
| Analysis triggering (reuse existing) | HIGH | MEDIUM | P1 |
| Status API endpoints | MEDIUM | LOW | P1 |
| Retry with exponential backoff | MEDIUM | LOW | P1 |
| SSE notification | MEDIUM | MEDIUM | P2 |
| Subprocess calculation sandbox | MEDIUM | MEDIUM | P2 |
| Summary vs full-text handling | LOW | MEDIUM | P2 |
| Watchlist management API | LOW | LOW | P2 |
| Processing audit trail | MEDIUM | LOW | P2 |
| HKEX monitoring | HIGH | HIGH | P3 |
| OCR fallback | LOW | HIGH | P3 |
| Webhook notifications | LOW | MEDIUM | P3 |
| Batch screening automation | HIGH | HIGH | P3 |
| Incremental RAG updates | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.1 -- the pipeline cannot function without these; forms the minimum viable automated pipeline
- P2: Should have -- enhances the pipeline but not strictly required for it to work end-to-end
- P3: Nice to have / future -- extends capabilities for post-validation phases

---

## Competitor Feature Analysis

| Feature | TongHuaShun (iFinD) | Xueqiu | EastMoney | StockValueFinder Pipeline |
|---------|---------------------|--------|-----------|--------------------------|
| Automated report monitoring | Enterprise feature (paid API) | None | Basic alerting | Free, self-hosted, CSI 300 scoped |
| Financial report PDF download | Via iFinD terminal | Manual (user downloads) | Manual download | Automated from CNInfo |
| AI-powered report analysis | Limited (paid "AI研报") | Community-written summaries | Basic AI summaries | Automated M-Score + DCF + yield gap |
| RAG over annual reports | Not available for retail | Not available | Not available | Automated ingestion into Qdrant |
| Fraud detection on new reports | Not automated | Not available | Not available | M-Score + F-Score auto-triggered on disclosure |
| Pipeline status monitoring | Enterprise dashboard | N/A | N/A | REST API + SSE notifications |
| Historical report archive | Full (paid) | User-uploaded | Limited | Automatic accumulation via pipeline |

### Competitive Positioning for Pipeline

The pipeline transforms StockValueFinder from a "pull" tool (user requests analysis for a specific stock) into a "push" tool (system proactively monitors, processes, and alerts). This is a fundamental UX upgrade:

1. **Zero manual effort**: New reports are detected, downloaded, parsed, analyzed, and indexed automatically. The user arrives to find fresh analysis already waiting.
2. **Timeliness**: During reporting season (Jan-Apr), the system detects new filings within 24 hours and has full analysis ready shortly after. No other retail tool offers this for A-shares.
3. **Comprehensive coverage**: Every CSI 300 stock is monitored simultaneously. A human analyst cannot track 300 disclosure schedules manually.

---

## Sources

- AKShare documentation: `stock_report_disclosure` API for disclosure schedules (confirmed via Context7 -- returns ticker, appointment dates, change dates, actual disclosure date)
- AKShare documentation: `stock_yysj_em` API for Eastmoney disclosure times (confirmed via Context7 -- alternative data source with similar structure)
- arq documentation: job uniqueness via `_job_id`, cron jobs, worker configuration, retry behavior (confirmed via Context7 from arq-docs.helpmanual.io)
- APScheduler documentation: AsyncScheduler, IntervalTrigger, CronTrigger, FastAPI lifespan integration (confirmed via Context7 from agronholm/apscheduler)
- Existing codebase: `DocumentService.process_upload()` for RAG pipeline integration (pdf_processor -> chunks -> embeddings -> Qdrant)
- Existing codebase: `AKShareClient._run_sync()` for thread pool execution pattern with rate limiting (0.5s minimum interval)
- Existing codebase: `CacheManager` for Redis integration patterns (connection pool, graceful degradation)
- Existing codebase: `BaseRepository` generic pattern for new pipeline_tasks repository
- Existing codebase: frozen dataclass config pattern (PipelineConfig should follow RAGConfig, ValuationConfig conventions)
- Project decisions: arq + Redis over Celery + RabbitMQ (confirmed in PROJECT.md Key Decisions)
- Project decisions: APScheduler for scheduling (confirmed in PROJECT.md Key Decisions)
- Project decisions: PyMuPDF first, OCR as fallback (confirmed in PROJECT.md Key Decisions)
- Project decisions: A-share first, HK later (confirmed in PROJECT.md Key Decisions)
- Project decisions: API/HTTP over Playwright (confirmed in PROJECT.md Key Decisions)

---
*Feature research for: Smart Financial Report Pipeline (v1.1 milestone)*
*Researched: 2026-05-01*
