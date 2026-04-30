# Pitfalls Research

**Domain:** Smart Financial Report Pipeline (v1.1 milestone) -- scheduled monitoring, PDF downloading, idempotent processing, state machine, task queue integration with existing FastAPI + PostgreSQL + Redis + Qdrant backend
**Researched:** 2026-05-01
**Confidence:** HIGH (Context7-verified library docs + codebase-verified integration points + domain knowledge)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, silent failures, or system instability.

---

### Pitfall 1: APScheduler Double-Start Under Uvicorn --reload

**What goes wrong:**
When running `uvicorn` with `--reload` during development, the file watcher spawns a new process. If `AsyncIOScheduler.start()` is called in the FastAPI lifespan, the scheduler starts once in the parent process and again in the reloaded child process. Jobs run twice per interval, causing duplicate announcement polls and double-enqueued download tasks.

**Why it happens:**
APScheduler uses `AsyncIOScheduler` which binds to the current event loop. Uvicorn's reloader creates a subprocess that re-executes the lifespan startup. The scheduler has no built-in awareness of parent/child process relationships. The PROJECT.md already specifies APScheduler for scheduling, and the existing `main.py` lifespan pattern (lines 30-66) uses `@asynccontextmanager async def lifespan(app)` -- adding scheduler start there without a guard triggers this immediately.

**How to avoid:**
1. Guard scheduler start with `os.environ.get("RUN_MAIN")` or a file-based lock -- uvicorn reloader sets `RUN_MAIN="true"` only in the child process.
2. Alternatively, use `APScheduler` with a PostgreSQL job store (the project already has PostgreSQL) so jobs persist across restarts and duplicate schedules are rejected via `ConflictPolicy.replace`.
3. In production, run without `--reload` and consider running the scheduler in a separate process from the API server if the task volume warrants it.

**Warning signs:**
- Announcement watcher fires twice per interval in logs.
- Duplicate download tasks appear in Redis queue with different job IDs but same URL.
- `scheduler.get_jobs()` returns two copies of every scheduled job.

**Phase to address:**
Phase 1 (Smart Watcher -- scheduling infrastructure) -- must be solved before any polling begins.

---

### Pitfall 2: Arq Worker Not Running -- Tasks Silently Queue Forever

**What goes wrong:**
`arq` is a two-part system: an enqueue side (your FastAPI app) and a worker side (a separate process running `arq worker_module.WorkerSettings`). If you call `await redis.enqueue_job('download_pdf', url)` from a FastAPI route but no worker process is running, the task sits in the Redis sorted set forever. No error is raised, no log is written, nothing fails visibly. The system appears to "accept" tasks but never processes them.

**Why it happens:**
Arq's design separates enqueue from execution by design. The enqueue call returns a `Job` object, not a result. There is no built-in health check that alerts when a queue has tasks but no consumers. Developers often test the enqueue path, verify the Redis key exists, and assume things are working.

**How to avoid:**
1. Add a health-check endpoint to FastAPI that calls `redis.zcard(queue_name)` and alerts if queue depth exceeds a threshold.
2. Add a startup validation in the FastAPI lifespan that logs whether an arq worker is reachable (use `redis.info()` to check connected clients).
3. In Docker Compose, run the arq worker as a separate service with `restart: unless-stopped`.
4. Add a `cron` job in arq's `WorkerSettings.cron_jobs` that sends a heartbeat to a Redis key every minute -- the health check can verify this key's age.

**Warning signs:**
- Queue depth grows but no tasks complete.
- `redis.zcard("arq:queue")` returns a large number.
- No worker process logs appear after enqueue.
- The `_job_id` uniqueness check (enqueue returns `None`) masks the problem because it means a previous job is still queued.

**Phase to address:**
Phase 1 (Task Queue Setup) -- the worker must be running before any pipeline features work.

---

### Pitfall 3: Annual Report PDFs Exceed Memory -- OOM on 200+ Page Documents

**What goes wrong:**
A-share annual reports are frequently 200-400 pages, with embedded images, tables, and fonts. The existing `pdf_processor.py` calls `pymupdf.open(stream=pdf_bytes, filetype="pdf")` which loads the entire document into memory. For a 400-page PDF with embedded images, this can consume 500MB-1GB of RAM. If the pipeline processes multiple reports concurrently (CSI 300 constituents, potentially dozens of reports during earnings season), the worker process exhausts memory and gets killed by the OS OOM killer. No graceful error, no retry -- the worker process just dies.

**Why it happens:**
PyMuPDF's `open()` loads shared resources (fonts, images, color spaces) for the entire document upfront. The existing codebase loads the full `pdf_bytes` into memory before passing to `extract_pdf_content`. The `DocumentService.process_upload` does not set any concurrency limit. If 10 annual reports are queued simultaneously, 10 workers each load a full PDF into memory.

**How to avoid:**
1. Process PDFs in page batches using `insert_pdf(src, from_page=i, to_page=i+49)` followed by `pymupdf.TOOLS.store_shrink(100)` to free the MuPDF cache between batches (verified in PyMuPDF docs).
2. Set arq's `max_burst` or use `functools.partial` with a semaphore to limit concurrent PDF processing tasks to 2-3 at a time.
3. Set `keep_result` to a reasonable TTL in arq's `func()` wrapper -- don't keep full PDF bytes in Redis result keys.
4. Stream PDF downloads directly to disk (tempfile) rather than loading into memory, then process from disk with `pymupdf.open(filepath)`.
5. Add a file-size check before processing (the existing `rag_config.MAX_FILE_SIZE_MB` is a good pattern to follow).

**Warning signs:**
- Worker process killed with signal 9 (OOM) during earnings season.
- Memory usage spikes correlate with PDF download batch processing.
- `dmesg` shows `Out of memory: Killed process` for the arq worker.
- Processing succeeds for small reports (50 pages) but fails for large ones (300+ pages).

**Phase to address:**
Phase 2 (Processing Pipeline) -- memory management must be built into the PDF processing step from day one, not bolted on later.

---

### Pitfall 4: Idempotency Key Collision -- Same Report Processed Twice With Different Metadata

**What goes wrong:**
The PROJECT.md specifies deduplication using "source ID + SHA256 + business key." If the deduplication key is constructed inconsistently (e.g., using report title which changes between announcement and final filing, or using download URL which includes a timestamp token), the same annual report gets processed twice with different task IDs. Each run generates new Qdrant vectors and new database records, creating duplicate analysis results that confuse users.

**Why it happens:**
A-share announcement data from different sources (CNINFO announcements, SSE disclosures, SZSE disclosures) use different identifiers for the same report. A preliminary earnings announcement and the final annual report may share the same stock ticker and fiscal year but have different CNINFO announcement IDs. If the deduplication key uses announcement ID, both get processed. If it uses ticker+fiscal_year+report_type, the preliminary blocks the final from being processed.

**How to avoid:**
1. Define the deduplication key as `{ticker}:{fiscal_year}:{report_type}:{source_hash}` where `source_hash` is SHA256 of the PDF bytes (not the URL or announcement ID). This guarantees: same PDF = same key, different PDF = different key.
2. Check deduplication BEFORE downloading the PDF -- use announcement ID + title + date as a "soft" key for the watcher, and SHA256 as the "hard" key for the processor.
3. Store the deduplication key in PostgreSQL with a UNIQUE constraint, not just in Redis. Redis keys can expire or be lost; a UNIQUE constraint is permanent.
4. Use arq's `_job_id` parameter (verified in arq docs: `enqueue_job` with `_job_id` returns `None` if a job with that ID already exists in the queue) as a first gate, backed by the database UNIQUE constraint as a second gate.

**Warning signs:**
- Same ticker+fiscal_year appears multiple times in `financial_reports` table.
- Qdrant search returns duplicate chunks for the same report section.
- Analysis API returns different risk scores for the same stock on consecutive calls.
- Redis queue has jobs with different IDs pointing to the same PDF URL.

**Phase to address:**
Phase 1 (Task Management -- deduplication schema) and Phase 2 (Processing Pipeline -- SHA256 check). Both phases must agree on the deduplication key format.

---

### Pitfall 5: State Machine Invalid Transition -- Stuck Tasks That Cannot Progress or Retry

**What goes wrong:**
The PROJECT.md specifies states: `PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE/FAILED`. If a task crashes during the DOWNLOADING state (e.g., network timeout, worker OOM), the database record stays in DOWNLOADING forever. No retry logic triggers because the task is not in PENDING or FAILED. The system has a growing population of permanently stuck tasks.

**Why it happens:**
The state machine is stored in PostgreSQL, but the transition logic lives in the arq worker. If the worker crashes (OOM, unhandled exception, process kill), there is no cleanup code that moves DOWNLOADING back to PENDING or FAILED. The existing `DocumentService.process_upload` uses a simple `pending -> processing -> completed/failed` pattern (verified in `document_service.py:108-169`), but it has the same vulnerability -- if the process dies between "processing" and "completed/failed", the record stays in "processing" forever.

**How to avoid:**
1. Add a `last_updated_at` timestamp column to the pipeline task table.
2. Create a "stuck task reaper" cron job (run via APScheduler or arq cron) that finds tasks in non-terminal states where `last_updated_at` is older than a threshold (e.g., 30 minutes for DOWNLOADING, 2 hours for ANALYZING) and resets them to PENDING or FAILED.
3. Wrap each state transition in a try/finally that always sets a terminal or retryable state.
4. Use PostgreSQL advisory locks or `SELECT ... FOR UPDATE SKIP LOCKED` when claiming PENDING tasks, so two workers cannot claim the same task.
5. Consider using the `transitions` library (verified: supports hierarchical states, error callbacks, and invalid transition guards) for the state machine definition rather than ad-hoc if/elif chains.

**Warning signs:**
- Tasks remain in DOWNLOADING or ANALYZING for hours.
- No stuck-task alerting exists.
- Worker restart does not affect stuck tasks (they are in the database, not in Redis).
- The retry counter for stuck tasks never increments.

**Phase to address:**
Phase 2 (State Machine) -- the reaper and transition guards must ship with the initial state machine implementation, not as a follow-up.

---

### Pitfall 6: AKShare/efinance Rate Limiting During Batch Earnings Season Polling

**What goes wrong:**
The watcher polls for new announcements. During earnings season (January-April for A-shares), hundreds of CSI 300 companies file within days of each other. If the watcher discovers 50 new reports and enqueues 50 download tasks that all hit AKShare or efinance, the existing 0.5s rate limit in `AKShareClient._run_sync` (verified: `akshare_client.py:110-113`) means 50 sequential requests take 25+ seconds per task. But worse, the watcher itself may also be hitting AKShare for announcement data simultaneously. East Money drops connections when it detects excessive requests from the same IP.

**Why it happens:**
The existing rate limiter in `AKShareClient` is per-client-instance: `self._last_request_time`. Multiple code paths (watcher polling, data service fetching, rate client) each create their own client instance with their own rate limiter. There is no global rate limit across the application. During batch processing, the watcher and the data service both hit East Money simultaneously.

**How to avoid:**
1. Create a global rate limiter (semaphore or token bucket) that all AKShare/efinance calls go through, regardless of which client instance makes the call.
2. Add jitter to the watcher's polling interval (e.g., `interval +/- 10%`) to avoid thundering herd if multiple instances are running.
3. Cache announcement lists aggressively -- if the watcher polls every 30 minutes, the announcement list for a given date rarely changes within that window.
4. Use the `_job_try` parameter in arq's `Retry` exception to implement exponential backoff on download failures (verified in arq docs: `Retry(defer=ctx['job_try'] * 5)`).

**Warning signs:**
- AKShare requests start returning connection resets or empty DataFrames during earnings season.
- Download tasks fail with timeout errors that succeed on retry.
- Multiple `AKShareClient._run_sync` calls show overlapping request timestamps in logs.
- East Money returns HTTP 403 or drops TCP connections.

**Phase to address:**
Phase 1 (Smart Watcher) -- global rate limiting must be established before the watcher starts polling.

---

### Pitfall 7: Redis Connection Pool Exhaustion Between FastAPI and Arq

**What goes wrong:**
The existing system uses Redis for caching with a `ConnectionPool` created in `CacheManager.__init__` (verified: `cache.py:40`). The new pipeline adds arq, which also creates Redis connections via `create_pool(RedisSettings())`. If the FastAPI app uses `redis://localhost:6380/0` (the default from `config.py:77`) and arq worker also connects to the same Redis database, both share the same Redis instance but with separate connection pools. Under load (many concurrent API requests + background tasks processing), the combined pool sizes can exceed Redis's `maxclients` setting, causing connection-refused errors.

**Why it happens:**
The existing `CacheManager` creates a `ConnectionPool` without setting `max_connections` (verified: `cache.py:40`). The default for `redis-py` is `2**31` connections, which is fine for the pool but can overwhelm Redis server-side limits. Arq's `create_pool` also creates its own connections. If Redis has a low `maxclients` (common in Docker default configs), the combined connections exceed the limit.

**How to avoid:**
1. Set explicit `max_connections` on both the CacheManager pool and arq's Redis pool.
2. Consider using different Redis databases (e.g., DB 0 for cache, DB 1 for arq queue) to isolate concerns.
3. Share a single `ArqRedis` connection pool between FastAPI (for enqueue) and the worker (for dequeue) using arq's `create_pool` with the same `RedisSettings`.
4. Monitor Redis `connected_clients` via a health-check endpoint.
5. The existing `init_cache()` in `dependencies.py` returns a `CacheManager` stored in `app.state.cache` -- the arq pool should similarly be stored in `app.state.arq_pool` and initialized in the lifespan.

**Warning signs:**
- Redis returns `max number of clients reached` errors.
- FastAPI API requests fail with `CacheError` during heavy pipeline processing.
- Arq worker logs show connection timeouts.
- `redis-cli info clients` shows `connected_clients` approaching `maxclients`.

**Phase to address:**
Phase 1 (Task Queue Setup) -- connection pool configuration must be established when arq is first integrated.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using AKShare announcement functions for watcher instead of CNINFO official API | No registration, no API key, faster to implement | AKShare announcement scraping breaks when East Money changes their HTML structure; field names are unstable (already flagged as tech debt in PROJECT.md) | MVP only -- plan CNINFO open platform API integration for production |
| Storing task state only in Redis (not PostgreSQL) | Faster reads, simpler code | All task state lost on Redis restart; no audit trail; no relational queries for stuck tasks | Never -- use PostgreSQL for persistent state, Redis for transient queue |
| Processing PDFs fully in memory (current pattern) | Simpler code, matches existing `DocumentService.process_upload` | OOM on large annual reports, cannot scale to concurrent processing | Never for annual reports -- batch processing required from day one |
| Using `BackgroundTasks` instead of arq for pipeline steps | No additional infrastructure, works within FastAPI process | Tasks die when server restarts; no retry; no deduplication; blocks API workers | Only for trivial fire-and-forget notifications, never for the main pipeline |
| Skipping SHA256 deduplication and using only announcement ID | Faster processing (no download needed for dedup check) | Same report processed from different announcement sources; duplicate Qdrant vectors | Never -- SHA256 is essential for correctness |
| Hardcoding polling interval (e.g., every 30 minutes) | Simple configuration | All instances poll simultaneously; no adaptation to filing density (low activity at night, high during earnings season) | MVP only -- add jitter and adaptive intervals for production |

## Integration Gotchas

Common mistakes when connecting the pipeline to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Arq + FastAPI lifespan | Creating `ArqRedis` pool inside a route handler (new connection per request) | Create pool once in FastAPI lifespan, store in `app.state.arq_pool`, inject via dependency |
| Arq worker + SQLAlchemy | Sharing `AsyncSession` between FastAPI request context and arq worker context (different event loops) | Worker creates its own `async_session_maker` in `on_startup` context hook (verified in arq docs: `on_startup`/`on_shutdown` for dependency injection) |
| Pipeline + existing DocumentService | Calling `DocumentService.process_upload` directly from arq task (requires `AsyncSession` which needs an event loop bound to the worker, not FastAPI) | Extract the PDF parsing + chunking + embedding logic into standalone functions that take a session parameter; call from both DocumentService and arq task |
| Qdrant upsert from worker | Using the singleton `QdrantVectorStore()` with default localhost URL from worker container (different network than FastAPI container) | Pass Qdrant URL as environment variable to worker container; use Docker service name for resolution |
| Notification (SSE) + arq task completion | Trying to send SSE from arq worker (worker has no access to FastAPI's response objects) | Write completion status to PostgreSQL; FastAPI SSE endpoint polls the database or uses Redis pub/sub to be notified of completion |
| AKShare in arq worker | Calling AKShare sync functions directly in async arq task (blocks the worker event loop) | Use `asyncio.to_thread()` or `loop.run_in_executor()` (existing pattern in `akshare_client.py:81-103` already does this) |
| Alembic migration for pipeline tables | Adding pipeline tables to the same migration as existing tables, breaking backward compatibility | Create a separate Alembic migration for pipeline tables; existing 8 ORM models should not be modified |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential PDF processing of queued reports | Earnings season backlog grows faster than processing capacity | Batch processing with configurable concurrency limit (2-3 concurrent PDF workers) | 10+ reports queued simultaneously |
| Full PDF re-processing on every pipeline run | Same 300-page report gets parsed, chunked, and embedded every time | Check SHA256 before processing; skip if unchanged and Qdrant already has chunks for this document_id | Any repeated processing of the same report |
| Embedding generation without batching | One HTTP call to embedding API per chunk (100+ calls per 300-page report) | Batch embedding requests (existing `BGEEmbeddingClient` should support batch mode) | Reports with 50+ chunks |
| Redis cache key collision between pipeline and existing cache | Pipeline uses `pipeline:{ticker}:{year}` key format that collides with existing `svf:{version}:{method}:{args}` format | Use distinct key prefixes: existing cache uses `svf:`, pipeline uses `pipe:` | Immediate if key formats overlap |
| Unbounded task queue growth | Redis memory grows linearly with queued tasks; queue scan time increases | Set `keep_result` TTL in arq `func()` wrapper; periodically clean completed jobs | 1000+ tasks in queue |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Downloading PDFs from exchange websites without validating Content-Type | Malicious server could return executable file disguised as PDF | Validate `Content-Type: application/pdf` header and PDF magic bytes (`%PDF-`) before processing |
| Storing downloaded PDF file paths in database without sanitization | Path traversal if file names from announcement metadata contain `../` sequences | Sanitize file names: strip path separators, use UUID-based storage paths, validate file extension |
| No timeout on PDF download requests | Worker hangs indefinitely if exchange server stops responding; blocks queue | Set explicit `timeout` on `httpx` download requests (30s connect, 300s read for large PDFs) |
| Worker process running with full database credentials | If worker is compromised (e.g., via malicious PDF), attacker gets full DB access | Use separate database users for worker (INSERT/UPDATE on pipeline tables only) vs API (SELECT on all tables) |
| Logging full PDF URLs with authentication tokens | Some exchange download URLs contain session tokens that expire but could be reused | Strip query parameters from logged URLs; log only ticker + report type + date |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Task Queue:** Worker process runs and picks up tasks -- but no health-check endpoint verifies the worker is alive. Test: stop the worker process, enqueue a task, wait 5 minutes, verify an alert fires.
- [ ] **Deduplication:** Same report URL is not enqueued twice -- but what if the same report appears from two different sources (CNINFO + SSE)? Test: enqueue the same annual report via two different announcement sources, verify only one processing task runs.
- [ ] **State Machine:** All happy-path transitions work -- but what about the crash-recovery path? Test: kill the worker process (SIGKILL) during DOWNLOADING state, verify the reaper resets the task to PENDING within the timeout window.
- [ ] **Notification:** SSE endpoint sends completion events -- but what if the SSE client disconnects and reconnects? Test: disconnect SSE client during processing, reconnect, verify the client receives the completion event or can poll for status.
- [ ] **PDF Processing:** Existing `extract_pdf_content` works for test PDFs -- but does it handle scanned annual reports (image-only PDFs)? Test: feed a scanned 2020 annual report (common for smaller companies) and verify graceful failure, not silent empty output.
- [ ] **Rate Limiting:** Watcher polls at configured interval -- but what about the retry backoff? Test: force a download failure, verify the retry delay increases exponentially and does not hammer the source.
- [ ] **Integration:** Pipeline triggers analysis (M-Score, DCF) after parsing -- but does it use the same data sources as the existing API? Test: trigger pipeline for a stock, then call the analysis API for the same stock, verify both use the same financial data.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| APScheduler double-start | LOW | Restart uvicorn without `--reload`; add the process guard; redeploy |
| Stuck tasks in DOWNLOADING/ANALYZING | MEDIUM | Run manual SQL: `UPDATE pipeline_tasks SET status='PENDING', retry_count=retry_count+1 WHERE status IN ('DOWNLOADING','ANALYZING') AND last_updated_at < now() - interval '1 hour';` then restart worker |
| OOM kill on large PDF | MEDIUM | Add batch processing and memory limits to the PDF processor; reprocess failed tasks; deploy and restart worker |
| Duplicate Qdrant vectors from double processing | HIGH | Query Qdrant for duplicate `document_id + page + chunk_type` combinations; delete duplicates; verify `financial_reports` table has no duplicates via UNIQUE constraint |
| Redis connection exhaustion | LOW | Set `max_connections` on pool configs; restart Redis and worker; add monitoring |
| AKShare rate-limit ban | LOW | Wait for cooldown (usually 1-24 hours); implement global rate limiter; reprocess failed tasks |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| APScheduler double-start | Phase 1: Smart Watcher | Run with `--reload`, verify single scheduler instance in logs |
| Arq worker not running | Phase 1: Task Queue Setup | Stop worker, enqueue task, verify health-check detects queue buildup |
| PDF OOM on large reports | Phase 2: Processing Pipeline | Process a 400-page annual report, verify memory stays under limit |
| Idempotency key collision | Phase 1: Task Management (schema) + Phase 2: SHA256 check | Enqueue same report twice, verify second enqueue returns None or is rejected by UNIQUE constraint |
| State machine stuck tasks | Phase 2: State Machine | Kill worker mid-processing, verify reaper resets task within timeout |
| Rate limiting during earnings season | Phase 1: Smart Watcher | Simulate 50 simultaneous report discoveries, verify no connection resets |
| Redis pool exhaustion | Phase 1: Task Queue Setup | Run load test with concurrent API requests + pipeline tasks, verify no connection errors |

## Sources

- Arq official documentation (Context7-verified): job uniqueness via `_job_id`, `Retry` exception with deferral, worker `on_startup`/`on_shutdown` context hooks, `func()` wrapper for `max_tries`/`keep_result`/`timeout` settings
- APScheduler official documentation (Context7-verified): `AsyncScheduler` with FastAPI lifespan integration, `ConflictPolicy.replace` for duplicate schedule prevention, PostgreSQL data store for persistent jobs
- PyMuPDF official documentation (Context7-verified): batch processing pattern for large PDFs, `pymupdf.TOOLS.store_shrink(100)` for cache cleanup, `insert_pdf` for page-range extraction
- Transitions library documentation (Context7-verified): hierarchical state machines, error callbacks on transition failure, invalid transition guards
- Existing codebase analysis: `akshare_client.py` (rate limiter pattern), `cache.py` (Redis pool management), `data_service.py` (fallback chain), `document_service.py` (status tracking pattern), `main.py` (FastAPI lifespan), `db/base.py` (async engine/session), `config.py` (frozen dataclass configs)

---
*Pitfalls research for: Smart Financial Report Pipeline (v1.1 milestone)*
*Researched: 2026-05-01*
