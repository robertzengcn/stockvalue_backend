# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: M-Score Real Calculation (2/2 plans)
- [x] Phase 2: Redis Cache Integration (2/2 plans)
- [x] Phase 3: Test Coverage (6/6 plans)
- [x] Phase 4: RAG Pipeline (5/5 plans)

</details>

### v1.1 Smart Financial Report Pipeline (In Progress)

**Milestone Goal:** Build an event-driven pipeline that automatically monitors, downloads, parses, and processes A-share financial reports, ensuring the AI analysis engine stays current without manual data collection.

- [x] **Phase 5: Pipeline Foundation** — Config, DB schema, arq worker setup, state machine, and health-check endpoint
- [ ] **Phase 6: Smart Watcher** — Disclosure monitoring, new report detection, season-aware polling, and watchlist management
- [ ] **Phase 7: Report Processing** — PDF download, deduplication, RAG integration, analysis triggering, and concurrent processing
- [ ] **Phase 8: Task API, Notifications & Sandbox** — Status endpoints, manual trigger, SSE events, and subprocess calculation sandbox

## Phase Details

### Phase 5: Pipeline Foundation
**Goal**: The pipeline infrastructure is running — arq worker connects to Redis, state machine transitions are persisted to PostgreSQL, and a health-check endpoint confirms all subsystems are alive
**Depends on**: Phase 4 (existing RAG pipeline and services)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, PIPE-04, PIPE-05, PIPE-06
**Success Criteria** (what must be TRUE):
  1. PipelineConfig frozen dataclass controls polling schedule, rate limits, retry policy, concurrency, and watchlist scope with sensible defaults
  2. New pipeline_tasks and pipeline_documents tables exist in PostgreSQL via a separate Alembic migration, with no changes to existing tables
  3. arq worker process starts, connects to Redis, and is accessible from FastAPI via app.state.arq_pool for job enqueuing
  4. Pipeline state machine validates all transitions (PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE/FAILED), rejects invalid ones, and each transition is atomic with timestamp and error detail persisted
  5. GET /api/v1/pipeline/health returns 200 when watcher is active, worker is connected, and Redis queue is responsive — returns degraded status when any component is down
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — Pipeline foundation types: PipelineConfig, state machine, Pydantic models, ORM models, Alembic migration 009
- [x] 05-02-PLAN.md — arq worker skeleton with reaper cron, PipelineTaskRepository with atomic state transitions, FastAPI lifespan integration
- [x] 05-03-PLAN.md — Pipeline health-check endpoint and router integration

### Phase 6: Smart Watcher
**Goal**: The system automatically discovers newly disclosed A-share financial reports and enqueues processing jobs without any manual intervention
**Depends on**: Phase 5
**Requirements**: WATCH-01, WATCH-02, WATCH-03, WATCH-04, WATCH-05
**Success Criteria** (what must be TRUE):
  1. System polls A-share disclosure schedules on a configurable cron schedule using AKShare stock_report_disclosure API without errors
  2. System detects newly disclosed reports by comparing actual disclosure dates against last-processed timestamps and skips already-processed announcements
  3. Polling frequency is daily during high season (Jan-Apr) and weekly during off-season (May-Dec), driven by PipelineConfig
  4. User can configure which CSI 300 stocks to monitor via API, with default being all CSI 300 constituents from AKShare index_stock_cons
  5. Each newly detected report automatically enqueues an arq processing job without manual intervention
**Plans**: 3 plans

Plans:
- [ ] 06-01-PLAN.md — PipelineConfig season-aware fields, Pydantic models, ORM models, Alembic migration 010
- [ ] 06-02-PLAN.md — WatcherService, AKShare disclosure methods, repositories, WorkerSettings cron update
- [ ] 06-03-PLAN.md — Watchlist CRUD REST endpoints (POST/GET/DELETE)

### Phase 7: Report Processing
**Goal**: Downloaded reports are parsed, embedded into Qdrant, and analyzed by existing risk/valuation/yield services — with deduplication preventing redundant work and partial failure handled gracefully
**Depends on**: Phase 6
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-07, PIPE-08, PIPE-09, PIPE-10
**Success Criteria** (what must be TRUE):
  1. System downloads PDF files from CNInfo disclosure sources with rate limiting (0.5s minimum between requests) and stores them on local filesystem with database metadata record (source URL, SHA256 hash, file path, size)
  2. 3-tier deduplication prevents duplicate processing: source announcement ID (primary), SHA256 hash of PDF bytes (content), and business key ticker+fiscal_year+report_type (semantic)
  3. Downloaded PDFs are processed through existing DocumentService.process_upload() for chunking, embedding, and upsert into Qdrant without code changes to the RAG pipeline
  4. System automatically triggers RiskAnalyzer, DCFValuationService, and YieldAnalyzer after successful parsing, and if one analyzer fails, others' results are still persisted with the task state reflecting partial completion
  5. Multiple reports process concurrently via arq workers with configurable max_concurrent_tasks and per-ticker job uniqueness preventing duplicate simultaneous processing
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Task API, Notifications & Sandbox
**Goal**: Users can monitor pipeline status, trigger processing manually, receive real-time completion notifications via SSE, and calculations run in an isolated subprocess with resource limits
**Depends on**: Phase 7
**Requirements**: TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, SBOX-01, SBOX-02, SBOX-03, SBOX-04
**Success Criteria** (what must be TRUE):
  1. GET /api/v1/pipeline/status returns aggregate counts by state, last poll time, and next scheduled poll time
  2. GET /api/v1/pipeline/tasks lists tasks with filtering by state, ticker, date range, and pagination support
  3. POST /api/v1/pipeline/trigger accepts a ticker and enqueues a pipeline processing job that runs through the full state machine
  4. GET /api/v1/pipeline/events SSE endpoint pushes real-time task_created, task_completed, and task_failed events, handles client disconnect and reconnect with event replay within a configurable window
  5. Financial calculations execute in an isolated subprocess with configurable timeout (default 30s) and memory limits, receiving inputs as JSON via stdin and returning results as JSON via stdout — but pipeline works without it (falls back to in-process execution)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. M-Score Real Calculation | v1.0 | 2/2 | Complete | 2026-04-15 |
| 2. Redis Cache Integration | v1.0 | 2/2 | Complete | 2026-04-16 |
| 3. Test Coverage | v1.0 | 6/6 | Complete | 2026-04-17 |
| 4. RAG Pipeline | v1.0 | 5/5 | Complete | 2026-04-19 |
| 5. Pipeline Foundation | v1.1 | 3/3 | Complete | 2026-05-01 |
| 6. Smart Watcher | v1.1 | 0/3 | Planning complete | - |
| 7. Report Processing | v1.1 | 0/3 | Not started | - |
| 8. Task API, Notifications & Sandbox | v1.1 | 0/3 | Not started | - |
