# Requirements: StockValueFinder v1.1

**Defined:** 2026-05-01
**Core Value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## v1.1 Requirements

Requirements for Smart Financial Report Pipeline milestone. Each maps to roadmap phases.

### Monitoring (WATCH)

- [x] **WATCH-01**: System automatically polls A-share disclosure schedules using AKShare `stock_report_disclosure` API on a configurable cron schedule
- [x] **WATCH-02**: System detects newly disclosed reports by comparing actual disclosure dates against last-processed timestamps in the database
- [x] **WATCH-03**: System adapts polling frequency based on reporting season — daily during high season (Jan-Apr), weekly during off-season (May-Dec)
- [x] **WATCH-04**: User can configure which CSI 300 stocks to monitor via API (default: all CSI 300 constituents from `index_stock_cons`)
- [x] **WATCH-05**: System enqueues a processing job for each newly detected report without manual intervention

### Pipeline Processing (PIPE)

- [ ] **PIPE-01**: System downloads PDF files from disclosure sources (CNInfo) using httpx with rate limiting (0.5s minimum between requests) and proper headers
- [ ] **PIPE-02**: System stores downloaded PDFs on local filesystem (UPLOAD_DIR pattern) with database metadata record (source URL, SHA256 hash, file path, size)
- [ ] **PIPE-03**: System implements 3-tier deduplication: source announcement ID (primary), SHA256 hash of PDF bytes (content), business key ticker+fiscal_year+report_type (semantic)
- [x] **PIPE-04**: System tracks each report through a linear state machine: PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE / FAILED
- [x] **PIPE-05**: Each state transition is atomic, persisted to PostgreSQL, and includes timestamp and error detail (if failed)
- [x] **PIPE-06**: System retries failed tasks up to 3 times with exponential backoff (2s, 8s, 30s) before marking as permanently failed
- [ ] **PIPE-07**: System reuses existing DocumentService.process_upload() to chunk, embed, and upsert downloaded PDFs into Qdrant
- [ ] **PIPE-08**: System automatically triggers RiskAnalyzer, DCFValuationService, and YieldAnalyzer with fresh financial data after successful PDF parsing
- [ ] **PIPE-09**: System handles partial analysis failures — if one analyzer fails, others' results are still persisted and the task state reflects partial completion
- [ ] **PIPE-10**: System processes multiple reports concurrently via arq workers with configurable max_concurrent_tasks and per-ticker job uniqueness

### Task Management (TASK)

- [ ] **TASK-01**: User can query pipeline status via GET /api/v1/pipeline/status returning aggregate counts by state, last poll time, next scheduled poll time
- [ ] **TASK-02**: User can list pipeline tasks via GET /api/v1/pipeline/tasks with filtering by state, ticker, date range, and pagination support
- [ ] **TASK-03**: User can manually trigger pipeline processing for a specific ticker via POST /api/v1/pipeline/trigger
- [ ] **TASK-04**: System provides SSE endpoint (GET /api/v1/pipeline/events) that pushes real-time task_created, task_completed, and task_failed events to connected clients
- [ ] **TASK-05**: SSE endpoint handles client disconnect and reconnect gracefully, with event replay for missed events within a configurable window

### Calculation Sandbox (SBOX)

- [ ] **SBOX-01**: System executes financial calculations (M-Score, DCF, yield gap) in an isolated subprocess with configurable timeout (default 30s) and memory limits
- [ ] **SBOX-02**: Subprocess receives calculation inputs as JSON via stdin and returns results as JSON via stdout
- [ ] **SBOX-03**: System kills subprocess and returns CalculationError on timeout or memory limit breach
- [ ] **SBOX-04**: Subprocess sandbox is optional — pipeline works without it (calculations run in-process as today) but uses it when available

### Configuration & Infrastructure (CONF)

- [x] **CONF-01**: Pipeline behavior is controlled by a frozen PipelineConfig dataclass (polling schedule, rate limits, retry policy, concurrency, watchlist scope)
- [x] **CONF-02**: New database tables (pipeline_tasks, pipeline_documents) are created via Alembic migration separate from existing tables
- [x] **CONF-03**: arq worker pool is initialized during FastAPI lifespan startup and stored in app.state for dependency injection
- [x] **CONF-04**: Pipeline health-check endpoint verifies watcher is active, worker is connected, and Redis queue is responsive

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Future Pipeline Features

- **WATCH-F01**: HKEX (披露易) monitoring for Hong Kong stocks
- **WATCH-F02**: Multi-market watcher abstraction behind common interface
- **PIPE-F01**: OCR fallback for scanned PDFs (PaddleOCR)
- **PIPE-F02**: Summary vs full-text report handling with differentiated processing
- **PIPE-F03**: Incremental RAG updates — update only affected chunks in Qdrant
- **PIPE-F04**: Processing audit trail per report (detailed step-by-step log with timestamps and durations)
- **TASK-F01**: Webhook notification to external systems (DingTalk, WeChat Server酱)
- **TASK-F02**: Batch CSI 300 screening automation — scheduled full-universe comparative reports
- **CONF-F01**: Separate database users for worker (INSERT/UPDATE on pipeline tables) vs API (SELECT on all tables)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Celery + RabbitMQ | Arq + Redis sufficient for current volume; explicit project decision |
| APScheduler | Arq cron_jobs eliminates need; avoids two scheduling systems |
| Playwright/Selenium | API/HTTP preferred over browser automation; explicit project decision |
| PaddleOCR (this milestone) | PyMuPDF handles digital PDFs; OCR deferred to future phase |
| WebSocket for pipeline status | SSE simpler for one-directional push; no bidirectional need |
| Multi-market (HK/US) processing | A-share first; HK deferred; explicit project decision |
| Storing full PDF binary in database | PDFs on filesystem, metadata in DB; avoid DB bloat |
| User authentication | Single-user system for now; deferred |
| Frontend application | API-only for this milestone |
| Real-time webhook from CNInfo/EastMoney | Neither provides push APIs; polling is sufficient |
| Batch report generation for all CSI 300 | Individual stock processing first; batch later |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 5 | Complete |
| CONF-02 | Phase 5 | Complete |
| CONF-03 | Phase 5 | Complete |
| CONF-04 | Phase 5 | Complete |
| PIPE-04 | Phase 5 | Complete |
| PIPE-05 | Phase 5 | Complete |
| PIPE-06 | Phase 5 | Complete |
| WATCH-01 | Phase 6 | Complete |
| WATCH-02 | Phase 6 | Complete |
| WATCH-03 | Phase 6 | Complete |
| WATCH-04 | Phase 6 | Complete |
| WATCH-05 | Phase 6 | Complete |
| PIPE-01 | Phase 7 | Pending |
| PIPE-02 | Phase 7 | Pending |
| PIPE-03 | Phase 7 | Pending |
| PIPE-07 | Phase 7 | Pending |
| PIPE-08 | Phase 7 | Pending |
| PIPE-09 | Phase 7 | Pending |
| PIPE-10 | Phase 7 | Pending |
| TASK-01 | Phase 8 | Pending |
| TASK-02 | Phase 8 | Pending |
| TASK-03 | Phase 8 | Pending |
| TASK-04 | Phase 8 | Pending |
| TASK-05 | Phase 8 | Pending |
| SBOX-01 | Phase 8 | Pending |
| SBOX-02 | Phase 8 | Pending |
| SBOX-03 | Phase 8 | Pending |
| SBOX-04 | Phase 8 | Pending |

**Coverage:**
- v1.1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-05-01*
*Last updated: 2026-05-01 after roadmap creation*
