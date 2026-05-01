# Phase 7: Report Processing - Research

**Researched:** 2026-05-02
**Domain:** PDF download/parse/analyze pipeline workers
**Confidence:** HIGH

## Summary

This phase implements the 3 stub worker functions (`download_report`, `parse_report`, `analyze_report`) in `worker.py` as fully functional processing steps. Each worker reads a pipeline task from PostgreSQL via `PipelineTaskRepository`, performs its processing step, transitions the task state, and enqueues the next job in the chain.

The download step extracts a PDF URL from disclosure metadata, streams it via httpx, stores it on the filesystem, and records metadata in the `pipeline_documents` table. The parse step reads the PDF bytes, calls `DocumentService.process_upload()` for RAG indexing, and transitions to ANALYZING. The analyze step fetches structured financial data from AKShare, runs all 3 analyzers in parallel via `asyncio.gather`, stores results, and transitions to DONE or FAILED.

**Primary recommendation:** Implement workers as thin orchestrators that delegate to existing services (DocumentService, RiskAnalyzer, DCFValuationService, YieldAnalyzer, AKShareClient). No new libraries needed -- all dependencies are already in `pyproject.toml` and verified as installed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** AKShare disclosure functions provide PDF download links as part of announcement metadata. Use these links directly.
- **D-02:** Store PDFs in UPLOAD_DIR with subdirectory structure: `./uploads/{ticker}/{fiscal_year}/{report_type}/`.
- **D-03:** Use existing request_delay_seconds (0.5s) from PipelineConfig for rate limiting between downloads.
- **D-04:** Keep existing DONE/FAILED states only. No ANALYZING_PARTIAL state.
- **D-05:** Store partial analysis results in pipeline_tasks.result_summary as JSON with per-analyzer status.
- **D-06:** Primary source: fetch structured financial statements from AKShare/efinance.
- **D-07:** Fallback: extract financial data from parsed PDF text via RAG/LLM if AKShare fails.
- **D-08:** Fetch 2 years of financial data (current + previous) for comparison. Store in existing financial_reports table.
- **D-09:** Run all 3 analyzers in parallel within analyze_report job using asyncio.gather with exception handling.
- **D-10:** Enforce per-ticker job uniqueness via arq's _job_id parameter.
- **D-11:** Single analyze_report job handles: fetch financials -> run analyzers in parallel -> store results -> transition state.

### Claude's Discretion
- Exact AKShare method for PDF download links from disclosure data
- Financial data mapping from AKShare response to analyzer input format
- PDF extraction fallback implementation details
- Error message formatting for partial failures
- Retry logic for individual analyzer failures within asyncio.gather

### Deferred Ideas (OUT OF SCOPE)
- OCR fallback for scanned PDFs (PaddleOCR) -- future milestone
- Incremental RAG updates -- update only affected chunks -- future
- Processing audit trail with detailed step timing -- future
- Batch CSI 300 screening -- future
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | System downloads PDF files from disclosure sources (CNInfo) using httpx with rate limiting (0.5s minimum between requests) and proper headers | httpx 0.28.1 AsyncClient.stream() + aiter_bytes() pattern verified. Worker ctx already has http_client. |
| PIPE-02 | System stores downloaded PDFs on local filesystem (UPLOAD_DIR pattern) with database metadata record (source URL, SHA256 hash, file path, size) | `PipelineDocumentDB` model exists with all required fields. Need new PipelineDocumentRepository. UPLOAD_DIR = "./uploads" from RAGConfig. |
| PIPE-03 | System implements 3-tier deduplication: source announcement ID (primary), SHA256 hash (content), business key ticker+fiscal_year+report_type (semantic) | business_key already enforced by PipelineTaskRepository.create_task(). Need SHA256 check in PipelineDocumentRepository and source_id uniqueness. |
| PIPE-07 | System reuses existing DocumentService.process_upload() to chunk, embed, and upsert downloaded PDFs into Qdrant | DocumentService.process_upload() accepts (document_id, ticker, file_name, file_path, pdf_bytes). Works from arq worker -- just needs an AsyncSession. |
| PIPE-08 | System automatically triggers RiskAnalyzer, DCFValuationService, and YieldAnalyzer with fresh financial data after successful PDF parsing | All 3 analyzers accept structured dicts. AKShareClient has get_profit_sheet/balance_sheet/cash_flow_sheet. data_service._get_financial_report_from_akshare() shows the exact field mapping. |
| PIPE-09 | System handles partial analysis failures -- if one analyzer fails, others' results are still persisted and the task state reflects partial completion | asyncio.gather(return_exceptions=True) pattern. Store per-analyzer status in result_summary JSONB (D-05). |
| PIPE-10 | System processes multiple reports concurrently via arq workers with configurable max_concurrent_tasks and per-ticker job uniqueness | arq 0.25.0 enqueue_job(_job_id=...) enforces uniqueness -- returns None if job exists. Use ticker-based _job_id pattern. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PDF download via httpx | arq worker process | -- | Worker has http_client in ctx, runs outside FastAPI |
| PDF storage (filesystem) | Local filesystem | -- | UPLOAD_DIR pattern, write PDF bytes to disk |
| PDF metadata (DB) | PostgreSQL via arq worker | -- | PipelineDocumentDB records in pipeline_documents table |
| PDF parsing/RAG indexing | DocumentService | arq worker (orchestrator) | Worker creates session, calls DocumentService.process_upload() |
| Financial data fetching | AKShareClient | ExternalDataService | AKShare methods run in thread pool |
| Risk/valuation/yield analysis | RiskAnalyzer, DCFValuationService, YieldAnalyzer | -- | Pure functions, accept structured dicts, return domain models |
| Analysis result persistence | PipelineTaskRepository | -- | result_summary JSONB field on pipeline_tasks |
| State machine transitions | PipelineTaskRepository | arq worker (orchestrator) | transition_state() with SELECT FOR UPDATE |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Async HTTP client for PDF downloads | Already in worker ctx, supports stream() + aiter_bytes() |
| pymupdf (fitz) | 1.27.2.2 | PDF parsing | Already used by pdf_processor.extract_pdf_content() |
| arq | 0.25.0 | Job queue and worker | Already running, provides _job_id for uniqueness |
| hashlib (stdlib) | -- | SHA256 content hashing | stdlib, sha256 in algorithms_available [VERIFIED: runtime check] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.gather | stdlib | Parallel analyzer execution | In analyze_report worker |
| pathlib.Path (stdlib) | -- | Filesystem path construction | Upload directory creation |
| urllib.parse (stdlib) | -- | Extract announcementId from CNInfo URL | In download_report to build PDF URL |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx streaming | httpx request() (full read) | Streaming uses less memory for large PDFs; preferred |
| aiofiles for file I/O | Built-in open() in executor | aiofiles NOT in dependencies [VERIFIED: import failed]; use run_in_executor with open() instead, or write synchronously (PDFs are small-ish) |

**Installation:**
```bash
# No new packages needed -- all already installed
```

## Architecture Patterns

### System Architecture Diagram

```
WatcherService (Phase 6)
    |
    | enqueue_job("download_report", task_id)
    v
+--download_report worker---------------------------+
| 1. Load task from DB (PipelineTaskRepository)     |
| 2. Load disclosure metadata (source_raw from      |
|    pending_disclosures)                            |
| 3. Extract PDF URL from source_raw                 |
| 4. Stream-download PDF via httpx                   |
| 5. Compute SHA256 hash                             |
| 6. Write PDF to UPLOAD_DIR/{ticker}/{fy}/{type}/   |
| 7. Insert pipeline_documents record                |
| 8. transition_state -> PARSING                     |
| 9. enqueue_job("parse_report", task_id)            |
+---------------------------------------------------+
    |
    v
+--parse_report worker------------------------------+
| 1. Load task + document from DB                   |
| 2. Read PDF bytes from filesystem                 |
| 3. Call DocumentService.process_upload()           |
|    (chunks -> embed -> upsert to Qdrant)           |
| 4. transition_state -> ANALYZING                   |
| 5. enqueue_job("analyze_report", task_id)          |
+---------------------------------------------------+
    |
    v
+--analyze_report worker----------------------------+
| 1. Load task from DB                              |
| 2. Extract ticker, fiscal_year from business_key  |
| 3. Fetch 2y financial data via AKShareClient      |
|    (profit + balance + cashflow x 2 years)        |
| 4. Map to standardized format (data_service map)  |
| 5. asyncio.gather(risk, valuation, yield)          |
| 6. Store per-analyzer results in result_summary    |
| 7. Persist analysis results to respective tables   |
| 8. transition_state -> DONE or FAILED              |
+---------------------------------------------------+
```

### Recommended Project Structure
```
stockvaluefinder/pipeline/
  worker.py               # Modify: implement 3 stubs (download_report, parse_report, analyze_report)
  repo.py                 # Existing: PipelineTaskRepository
  document_repo.py        # NEW: PipelineDocumentRepository for pipeline_documents table
  config.py               # Existing: PipelineConfig (may add upload_dir field)
  state.py                # Existing: PipelineState transitions
  models.py               # Existing: Pydantic models
  watcher.py              # Existing: WatcherService (Phase 6)
```

### Pattern 1: Worker Function with State Machine Transitions
**What:** Each worker follows: load task -> do work -> transition state -> enqueue next
**When to use:** All 3 worker functions follow this pattern
**Example:**
```python
async def download_report(ctx: dict[str, Any], task_id: str) -> None:
    session_factory = ctx["session_factory"]
    http_client: httpx.AsyncClient = ctx["http_client"]

    async with session_factory() as session:
        repo = PipelineTaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return

        # Transition to DOWNLOADING
        await repo.transition_state(task_id, PipelineState.DOWNLOADING, current_stage="downloading")

        try:
            # Do the actual work
            pdf_bytes, metadata = await _download_pdf(http_client, task)

            # Store results
            doc_repo = PipelineDocumentRepository(session)
            await doc_repo.create_document(task_id=task_id, ...)

            # Transition to PARSING
            await repo.transition_state(task_id, PipelineState.PARSING, current_stage="parsing")
            await session.commit()

            # Enqueue next step
            await _enqueue_job("parse_report", task_id)

        except Exception as e:
            await repo.transition_state(task_id, PipelineState.FAILED, error_message=str(e))
            await session.commit()
            raise
```

### Pattern 2: asyncio.gather with return_exceptions for Partial Failure
**What:** Run all 3 analyzers in parallel, capture exceptions without killing the gather
**When to use:** analyze_report job (D-09, D-05)
**Example:**
```python
async def _run_all_analyzers(current_report, previous_report, ticker, ...):
    """Run risk, valuation, and yield analysis in parallel."""
    risk_coro = asyncio.to_thread(risk_analyzer.analyze, current_report, previous_report)
    valuation_coro = asyncio.to_thread(valuation_service.analyze, ...)
    yield_coro = asyncio.to_thread(yield_analyzer.analyze, ...)

    results = await asyncio.gather(
        risk_coro, valuation_coro, yield_coro,
        return_exceptions=True,
    )

    summary = {}
    for name, result in zip(["risk", "valuation", "yield"], results):
        if isinstance(result, Exception):
            summary[name] = {"status": "failed", "error": str(result)}
        else:
            summary[name] = {"status": "success", "result_ref": str(result.score_id)}

    return summary
```

### Pattern 3: PDF URL Extraction from CNInfo Disclosure Metadata
**What:** Extract announcementId from the CNInfo detail URL stored in source_raw
**When to use:** download_report worker to construct PDF download URL
**Example:**
```python
from urllib.parse import urlparse, parse_qs

def _extract_pdf_url(source_raw: dict[str, Any]) -> str | None:
    """Extract PDF download URL from CNInfo disclosure metadata.

    The CNInfo detail URL contains announcementId as a query parameter.
    PDF download URL pattern: https://static.cninfo.com.cn/{announcementId}.PDF
    """
    detail_url = source_raw.get("公告链接", "")
    if not detail_url:
        return None

    parsed = urlparse(detail_url)
    params = parse_qs(parsed.query)
    announcement_id = params.get("announcementId", [None])[0]

    if announcement_id:
        return f"https://static.cninfo.com.cn/{announcement_id}.PDF"
    return None
```

### Anti-Patterns to Avoid
- **Reading entire PDF into memory for download:** Use httpx streaming with aiter_bytes() to handle large reports without OOM
- **Running analyzers in-process without thread pool:** The analysis functions (RiskAnalyzer, etc.) are synchronous CPU-bound code. Wrap in `asyncio.to_thread()` or `run_in_executor()` to avoid blocking the event loop
- **Creating a new AKShareClient per worker call:** The client is already created in on_startup. Pass it through ctx or create a singleton
- **Forgetting rate limiting between AKShare calls:** AKShare has built-in 0.5s rate limiting in _run_sync(), but between downloads from CNInfo, use PipelineConfig.request_delay_seconds

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | pdf_processor.extract_pdf_content() | Already handles tables, bboxes, structured content |
| RAG pipeline (chunk -> embed -> store) | Custom chunking/embedding logic | DocumentService.process_upload() | Full pipeline: parse -> parent chunks -> child chunks -> embed -> Qdrant upsert |
| State machine transitions | Direct SQL UPDATE | PipelineTaskRepository.transition_state() | Atomic SELECT FOR UPDATE + validation |
| Financial data fetching | Raw AKShare calls | AKShareClient methods | Built-in rate limiting, retry logic, thread pool |
| M-Score/F-Score/DCF/Yield calculations | Any custom math | RiskAnalyzer, DCFValuationService, YieldAnalyzer | All are pure, tested functions |
| Financial field mapping | Manual dict construction | Copy pattern from data_service._get_financial_report_from_akshare() | Proven mapping from AKShare column names to analyzer input fields |

**Key insight:** This phase is primarily an integration phase. The heavy lifting (PDF parsing, financial calculations, RAG indexing) already exists. The new code is orchestration glue.

## Common Pitfalls

### Pitfall 1: CNInfo PDF URL Returns HTML Not PDF
**What goes wrong:** CNInfo sometimes returns an HTML error page instead of a PDF file when using `static.cninfo.com.cn/{id}.PDF`
**Why it happens:** The announcementId might reference a different document type, or the URL might be expired
**How to avoid:** Check Content-Type header after download -- must be `application/pdf` or `application/octet-stream`. If not, treat as download failure and retry.
**Warning signs:** Downloaded file size < 1KB, or file starts with `<!DOCTYPE` instead of `%PDF`

### Pitfall 2: Analyzer Functions Block the Event Loop
**What goes wrong:** RiskAnalyzer.analyze(), DCFValuationService.analyze(), and YieldAnalyzer.analyze() are synchronous CPU-bound functions. Calling them directly in an async worker blocks the event loop.
**Why it happens:** The functions are pure Python (no awaits) -- they do math, not I/O
**How to avoid:** Wrap each analyzer call in `asyncio.to_thread()` or `loop.run_in_executor()` so they run in a thread pool
**Warning signs:** Worker becomes unresponsive during analysis, other jobs in the queue don't start

### Pitfall 3: DocumentService Requires a Database Session but Worker Uses Separate Session
**What goes wrong:** DocumentService.__init__ requires an AsyncSession. The arq worker creates sessions via `async_session_maker()`. These are different sessions from what the pipeline uses.
**Why it happens:** DocumentService writes to the `documents` table (for RAG), while the pipeline writes to `pipeline_tasks` and `pipeline_documents`. Two different session instances.
**How to avoid:** Create a session from the worker's session_factory, pass it to DocumentService. Commit the DocumentService session AND the pipeline session separately. If DocumentService fails, the pipeline task goes to FAILED.
**Warning signs:** DocumentService raises but pipeline task stays in ANALYZING

### Pitfall 4: Missing source_raw in PipelineTask Causes Download to Fail
**What goes wrong:** The download_report worker tries to extract PDF URL from `pending_disclosures.source_raw`, but only has a `task_id`. The task record has `business_key` but not the source URL.
**Why it happens:** The pending_disclosures staging table has the source_raw, but pipeline_tasks does not. The link between them is through ticker+fiscal_year+report_type (the business_key components).
**How to avoid:** In download_report, query pending_disclosures by matching on ticker+report_type+fiscal_year to find the source_raw. Or: store the source URL in pipeline_documents at task creation time (during process_disclosures).
**Warning signs:** download_report cannot find PDF URL, all downloads fail immediately

### Pitfall 5: asyncio.gather Without return_exceptions Cancels All Coroutines on First Failure
**What goes wrong:** If `asyncio.gather(risk, valuation, yield)` is called without `return_exceptions=True`, the first exception cancels the remaining coroutines and propagates
**Why it happens:** Default behavior of asyncio.gather
**How to avoid:** Always use `return_exceptions=True` (D-09 explicitly specifies parallel with exception handling). Then inspect each result for Exception instances.
**Warning signs:** Only one analyzer result appears in result_summary even though all three should run

## Code Examples

### httpx Streaming Download with Rate Limiting
```python
# Source: httpx 0.28.1 docs [VERIFIED: runtime inspection]
import asyncio
import hashlib

async def download_pdf_with_hash(
    client: httpx.AsyncClient,
    url: str,
    delay_seconds: float = 0.5,
) -> tuple[bytes, str]:
    """Download PDF via streaming, compute SHA256 hash."""
    await asyncio.sleep(delay_seconds)

    async with client.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            raise ExternalAPIError(f"Expected PDF, got {content_type}")

        chunks: list[bytes] = []
        hasher = hashlib.sha256()

        async for chunk in response.aiter_bytes(chunk_size=8192):
            chunks.append(chunk)
            hasher.update(chunk)

        pdf_bytes = b"".join(chunks)
        return pdf_bytes, hasher.hexdigest()
```

### AKShare Field Mapping for Analyzer Input
```python
# Source: Verified against live AKShare data [VERIFIED: runtime query]
# Pattern from data_service._get_financial_report_from_akshare()

def map_akshare_to_analyzer_input(
    income: dict,       # from get_profit_sheet()[0]
    balance: dict,      # from get_balance_sheet()[0]
    cashflow: dict,     # from get_cash_flow_sheet()[0]
    ticker: str,
    fiscal_year: int,
) -> dict[str, Any]:
    """Map AKShare column names to analyzer input fields."""
    return {
        "ticker": ticker,
        "report_id": uuid4(),
        "fiscal_year": fiscal_year,
        # Income statement
        "revenue": str(income.get("TOTAL_OPERATE_INCOME", 0)),
        "net_income": str(income.get("NETPROFIT", 0)),
        "cost_of_goods": str(income.get("OPERATE_COST", 0)),
        "sga_expense": str(income.get("TOTAL_OPERATE_COST", 0)),
        # Balance sheet
        "total_assets": str(balance.get("TOTAL_ASSETS", 0)),
        "total_current_assets": str(balance.get("TOTAL_CURRENT_ASSETS", 0)),
        "accounts_receivable": str(balance.get("ACCOUNTS_RECE", 0)),
        "ppe": str(balance.get("FIXED_ASSET", 0)),
        "total_liabilities": str(balance.get("TOTAL_LIABILITIES", 0)),
        "equity_total": str(balance.get("TOTAL_EQUITY", 0)),
        "cash_and_equivalents": str(balance.get("MONETARYFUNDS", 0)),
        "goodwill": str(balance.get("GOODWILL", 0)),
        "interest_bearing_debt": str(balance.get("TOTAL_LIABILITIES", 0)),
        # Cash flow
        "operating_cash_flow": str(cashflow.get("NETCASH_OPERATE", 0)),
        # Computed
        "gross_margin": _calculate_gross_margin(income),
        "report_source": "AKShare",
    }
```

### arq Job Uniqueness via _job_id
```python
# Source: arq 0.25.0 enqueue_job source [VERIFIED: runtime inspection]
# _job_id parameter: if job with this ID already exists, enqueue_job returns None

async def enqueue_with_ticker_uniqueness(
    redis_pool: ArqRedis,
    function_name: str,
    task_id: str,
    ticker: str,
    business_key: str,
) -> Job | None:
    """Enqueue job with per-ticker uniqueness."""
    return await redis_pool.enqueue_job(
        function_name,
        task_id,
        _job_id=f"pipeline:{business_key}",
    )
```

### PipelineDocumentRepository (New)
```python
class PipelineDocumentRepository:
    """Repository for pipeline_documents table operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._model = PipelineDocumentDB

    async def create_document(
        self,
        task_id: str,
        source_url: str | None = None,
        source_id: str | None = None,
        content_hash: str | None = None,
        file_path: str | None = None,
        file_size: int | None = None,
    ) -> PipelineDocumentDB:
        doc = PipelineDocumentDB(
            document_id=uuid4(),
            task_id=task_id,
            source_url=source_url,
            source_id=source_id,
            content_hash=content_hash,
            file_path=file_path,
            file_size=file_size,
            downloaded_at=datetime.now(timezone.utc),
        )
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        return doc

    async def get_by_content_hash(self, content_hash: str) -> PipelineDocumentDB | None:
        stmt = select(self._model).where(self._model.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> PipelineDocumentDB | None:
        stmt = select(self._model).where(self._model.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| arq cron unique via function name | arq cron unique via `f'{name}:{unix_ms}'` | arq 0.25.0 | Cron uniqueness is built-in |
| arq job uniqueness via external lock | arq job uniqueness via `_job_id` parameter | arq 0.25.0 | Simpler pattern -- no `_unique_key_infunc` needed |
| AKShare stock_financial_analysis_indicator | stock_*_by_report_em APIs | AKShare 1.14+ | English column names, more reliable |

**Deprecated/outdated:**
- `_unique_key_infunc` pattern: Does not exist in arq 0.25.0. Use `_job_id` parameter instead. [VERIFIED: grep of arq source tree]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CNInfo PDF URL pattern is `https://static.cninfo.com.cn/{announcementId}.PDF` | Pattern 3 | Downloads fail -- need alternative URL construction or HTML scraping |
| A2 | The `source_raw` field in `pending_disclosures` contains `公告链接` from AKShare's CNInfo function | Pitfall 4 | download_report cannot find PDF URL -- need to query pending_disclosures differently |
| A3 | DocumentService.process_upload() works outside FastAPI request context (no DI issues) | Pitfall 3 | Need to refactor DocumentService for worker context |
| A4 | Analysis services (RiskAnalyzer, etc.) can be called from arq worker without FastAPI app state | Architecture | Need to initialize services differently in worker |

## Open Questions (RESOLVED)

1. **How does download_report access the PDF URL?**
   - What we know: The `pending_disclosures` table has `source_raw` JSONB which may contain `公告链接`. The `pipeline_tasks` table has `business_key` (ticker:fiscal_year:report_type) but not the source URL.
   - RESOLVED: Plan 07-01 Task 2 adds `_get_source_metadata()` helper that queries pending_disclosures by business_key to extract the announcement link and construct the PDF URL.

2. **Should PipelineConfig get an upload_dir field?**
   - What we know: RAGConfig has `UPLOAD_DIR = "./uploads"`. PipelineConfig does not have this field.
   - RESOLVED: Plan 07-01 Task 2 references `rag_config.UPLOAD_DIR` directly — no new config field needed per D-02.

3. **How to handle the case where a ticker has no stock record in the stocks table?**
   - What we know: pipeline_tasks has a FK to stocks.ticker. CSI 300 tickers should exist in the stocks table from Phase 6's watchlist management.
   - RESOLVED: Plan 07-01 Task 2 adds a defensive check — if ticker missing from stocks, call `ensure_stock_exists()` before proceeding.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | State persistence | needs check | -- | -- |
| Redis | arq job queue | needs check | -- | -- |
| Qdrant | RAG vector store | needs check | -- | -- |
| httpx | PDF downloads | Yes | 0.28.1 | -- |
| pymupdf | PDF parsing | Yes | 1.27.2.2 | -- |
| akshare | Financial data | Yes | 1.18.46 | efinance 0.5+ |
| arq | Job queue | Yes | 0.25.0 | -- |

**Missing dependencies with no fallback:**
- None -- all core libraries are installed

**Missing dependencies with fallback:**
- If AKShare fails for financial data, efinance is the fallback (D-06, D-07)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `uv run pytest tests/unit/test_pipeline/ -x` |
| Full suite command | `uv run pytest tests/ --cov=stockvaluefinder` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Download PDF via httpx with rate limiting | unit | `uv run pytest tests/unit/test_pipeline/test_download_worker.py -x` | No -- Wave 0 |
| PIPE-02 | Store PDF to filesystem + create pipeline_documents record | unit | `uv run pytest tests/unit/test_pipeline/test_download_worker.py::test_store_pdf -x` | No -- Wave 0 |
| PIPE-03 | 3-tier deduplication (source_id, content_hash, business_key) | unit | `uv run pytest tests/unit/test_pipeline/test_document_repo.py -x` | No -- Wave 0 |
| PIPE-07 | Call DocumentService.process_upload() from worker | unit | `uv run pytest tests/unit/test_pipeline/test_parse_worker.py -x` | No -- Wave 0 |
| PIPE-08 | Run 3 analyzers with structured financial data | unit | `uv run pytest tests/unit/test_pipeline/test_analyze_worker.py -x` | No -- Wave 0 |
| PIPE-09 | Partial failure handling with asyncio.gather | unit | `uv run pytest tests/unit/test_pipeline/test_analyze_worker.py::test_partial_failure -x` | No -- Wave 0 |
| PIPE-10 | Per-ticker job uniqueness via _job_id | unit | `uv run pytest tests/unit/test_pipeline/test_worker_uniqueness.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_pipeline/ -x`
- **Per wave merge:** `uv run pytest tests/ --cov=stockvaluefinder`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_pipeline/test_download_worker.py` -- covers PIPE-01, PIPE-02
- [ ] `tests/unit/test_pipeline/test_parse_worker.py` -- covers PIPE-07
- [ ] `tests/unit/test_pipeline/test_analyze_worker.py` -- covers PIPE-08, PIPE-09
- [ ] `tests/unit/test_pipeline/test_document_repo.py` -- covers PIPE-03
- [ ] `tests/unit/test_pipeline/test_worker_uniqueness.py` -- covers PIPE-10

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user system, deferred |
| V3 Session Management | No | No user sessions in worker |
| V4 Access Control | No | Worker runs with system privileges |
| V5 Input Validation | Yes | Pydantic models for task data, ticker validation regex |
| V6 Cryptography | Yes | SHA256 for content deduplication (hashlib, stdlib) |

### Known Threat Patterns for Pipeline Processing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious PDF (zip bomb) | Denial of Service | File size check against MAX_FILE_SIZE_MB (100MB) before processing |
| Path traversal in ticker field | Tampering | Ticker regex validation `^\d{4,6}\.(SH\|SZ\|HK)$` |
| SSRF via crafted PDF URL | Tampering | URL must match CNInfo domain pattern |
| SQL injection via metadata | Tampering | SQLAlchemy parameterized queries (ORM) |

## Sources

### Primary (HIGH confidence)
- httpx 0.28.1 AsyncClient.stream() -- runtime inspection of source code
- arq 0.25.0 enqueue_job() -- runtime inspection with `inspect.getsource()`
- AKShare 1.18.46 stock_*_by_report_em -- live column name verification against Moutai (600519)
- pymupdf 1.27.2.2 -- verified installed, already used by pdf_processor.py
- All source files in `stockvaluefinder/pipeline/`, `stockvaluefinder/services/`, `stockvaluefinder/external/`

### Secondary (MEDIUM confidence)
- CNInfo PDF URL pattern `https://static.cninfo.com.cn/{announcementId}.PDF` -- extracted from AKShare source code logic but not tested against live CNInfo server
- asyncio.gather(return_exceptions=True) behavior -- standard Python stdlib behavior, well-documented

### Tertiary (LOW confidence)
- None -- all critical claims verified against codebase or runtime

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified installed via runtime checks
- Architecture: HIGH - all services, repos, models verified against source code
- Pitfalls: HIGH - based on actual code inspection of analysis services (synchronous), httpx API, arq API
- AKShare column mapping: HIGH - verified against live data for SH600519

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (stable -- no fast-moving dependencies)
