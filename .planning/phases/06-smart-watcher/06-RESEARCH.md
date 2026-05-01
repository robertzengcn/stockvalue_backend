# Phase 6: Smart Watcher - Research

**Researched:** 2026-05-01
**Domain:** Disclosure monitoring, season-aware polling, watchlist management, report detection
**Confidence:** HIGH

## Summary

This phase builds the automated disclosure monitoring system on top of the Phase 5 pipeline infrastructure. The watcher polls A-share financial report disclosure schedules via AKShare (backed by CNInfo), detects newly disclosed reports, and enqueues processing jobs into the arq pipeline. Two new database tables (`watchlist` for user-configured stock monitoring scope, `watcher_state` for observability) are created alongside a `pending_disclosures` staging table that decouples polling from processing.

The core technical challenge is season-aware scheduling: the system must poll daily during reporting high season (Jan-Apr) and weekly during off-season (May-Dec), controlled by PipelineConfig. Arq's `cron()` function supports `month` and `weekday` parameters natively, enabling a single cron entry that only fires during configured months. The alternative approach -- a single daily cron that checks the current month at runtime -- is simpler and avoids maintaining two cron entries that could conflict.

The AKShare `stock_report_disclosure` function returns disclosure schedules from CNInfo with columns for stock code, name, first appointment date, change dates, and actual disclosure date. The CNInfo fallback (`stock_zh_a_disclosure_report_cninfo`) provides per-stock announcement-level detail including `announcementId`, `orgId`, and publication timestamps, enabling amendment detection.

**Primary recommendation:** Use a single daily cron (`hour=9, minute=0`) with runtime month-check for season-awareness (not two separate cron entries). Add `high_season_months` field to PipelineConfig as a frozenset for month-based detection.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Primary source: AKShare `stock_report_disclosure` API. Fallback: CNInfo announcement API via HTTP when AKShare fails or returns stale data.
- **D-02:** Immediate CNInfo fallback in the same poll cycle when AKShare fails -- no separate retry cycle needed.
- **D-03:** Monitor all report types: annual, semi-annual, Q1 quarterly, Q3 quarterly.
- **D-04:** Construct business_key from poll data as `ticker:fiscal_year:report_type` for deduplication. Matches existing pipeline_tasks unique constraint.
- **D-05:** Reprocess amended reports -- when a company re-submits a corrected report for the same fiscal year, create a new pipeline task.
- **D-06:** Detect amendments by comparing disclosure_date per business_key. If a new poll shows a later disclosure_date for an existing business_key, it's an amendment.
- **D-07:** Month-based season detection via PipelineConfig fields: `high_season_months` (default Jan-Apr) and corresponding cron schedules.
- **D-08:** High season: daily at 09:00 CST. Off-season: weekly Monday at 09:00 CST.
- **D-09:** Add `high_season_cron`, `off_season_cron`, `high_season_months` fields to PipelineConfig. The watcher cron checks current month and selects appropriate schedule.
- **D-10:** Check pipeline_tasks table for existing business_key. If not found -> new report. Simple SQL lookup on unique constraint.
- **D-11:** Two-phase architecture: poll cron writes disclosures to a `pending_disclosures` staging table. A separate worker job processes the staging table, detects new vs. amendment, and enqueues download jobs.
- **D-12:** Enqueue one arq job per new disclosure. Each job creates a pipeline task and processes independently.
- **D-13:** New `watchlist` table in PostgreSQL: ticker (PK), name, added_at, is_active. User adds/removes via REST API.
- **D-14:** Empty by default -- user must explicitly add stocks via API. No auto-seeding.
- **D-15:** Dedicated watchlist endpoints: POST /api/v1/pipeline/watchlist (add), GET (list), DELETE (remove). New Alembic migration 010.
- **D-16:** New `watcher_state` table: watcher_id, last_poll_time, last_akshare_success, last_cninfo_fallback, polls_count, errors_count. Updated each poll cycle.
- **D-17:** Single Alembic migration 010 for both watchlist and watcher_state tables. Keeps Phase 6 DB changes atomic.

### Claude's Discretion
- Exact AKShare client method signatures for `stock_report_disclosure` and `index_stock_cons`
- CNInfo HTTP client implementation details (URL, headers, parsing)
- Staging table schema for pending_disclosures
- Watcher service class structure and error handling
- Logging format and verbosity for watcher operations

### Deferred Ideas (OUT OF SCOPE)
- HKEX monitoring for Hong Kong stocks
- Multi-market watcher abstraction
- Batch import via Excel/text file
- Watchlist groups/tags
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WATCH-01 | System polls A-share disclosure schedules using AKShare `stock_report_disclosure` API on configurable cron schedule | `stock_report_disclosure(market="沪深京", period="YYYY年报")` verified [VERIFIED: inspect source]. Arq cron_jobs with `hour/minute/month/weekday` params verified [VERIFIED: arq 0.25.0 source] |
| WATCH-02 | System detects newly disclosed reports by comparing actual disclosure dates against last-processed timestamps | PipelineTaskRepository.get_by_business_key() exists [VERIFIED: repo.py]. `stock_report_disclosure` returns `实际披露` (actual disclosure date) column [VERIFIED: source] |
| WATCH-03 | System adapts polling frequency based on reporting season -- daily during high season, weekly during off-season | Arq cron supports `month` param for month-based filtering [VERIFIED: inspect]. PipelineConfig extends with `high_season_months` field following frozen dataclass pattern [VERIFIED: config.py] |
| WATCH-04 | User can configure which CSI 300 stocks to monitor via API | `index_stock_cons_csindex(symbol="000300")` returns constituent stocks with `成分券代码` and `成分券名称` [VERIFIED: source]. Watchlist table + REST API follows established patterns [VERIFIED: pipeline_routes.py, api.py] |
| WATCH-05 | System enqueues a processing job for each newly detected report without manual intervention | ArqRedis.enqueue_job() exists [VERIFIED: inspect]. WorkerSettings.functions list can be extended [VERIFIED: worker.py]. PipelineTaskRepository.create_task() handles dedup [VERIFIED: repo.py] |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Disclosure schedule polling | API / Backend (arq worker) | -- | Runs as arq cron job in worker process, not triggered by HTTP requests |
| CNInfo HTTP fallback | API / Backend (arq worker) | -- | Network calls from worker process, same poll cycle |
| New report detection | API / Backend (worker job) | Database / Storage | Reads pending_disclosures staging table, queries pipeline_tasks for dedup |
| Season-aware scheduling | API / Backend (arq cron) | -- | Month-based runtime check in cron function decides poll vs skip |
| Watchlist CRUD | API / Backend (FastAPI) | Database / Storage | REST API endpoints served by FastAPI, persisted to PostgreSQL |
| Watcher state observability | API / Backend (arq worker) | Database / Storage | Updated each poll cycle by watcher cron function |
| Pipeline job enqueuing | API / Backend (arq worker) | -- | Worker enqueues jobs to Redis via arq |
| CSI 300 constituent lookup | API / Backend (AKShareClient) | -- | Called from watcher to get default stock universe |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | 0.25.0 (installed) | Task queue + cron scheduler | Already in pyproject.toml from Phase 5. Cron function supports `month`, `weekday`, `hour`, `minute`, `job_id`, `unique` params. [VERIFIED: installed + inspect] |
| AKShare | 1.18.46 (installed) | A-share data source | Already in pyproject.toml. `stock_report_disclosure` returns disclosure schedules from CNInfo. `index_stock_cons_csindex` returns CSI 300 constituents. `stock_zh_a_disclosure_report_cninfo` provides per-stock CNInfo announcement detail. [VERIFIED: installed + inspect] |
| FastAPI | installed | REST API for watchlist | Existing framework. Watchlist CRUD endpoints follow established pattern. [VERIFIED: main.py] |
| SQLAlchemy 2.0 | installed | ORM for new tables | Async ORM with declarative base. New tables follow existing model pattern. [VERIFIED: db/models/] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | installed | CNInfo HTTP fallback direct calls | If AKShare's `stock_zh_a_disclosure_report_cninfo` wrapper is insufficient (e.g., need raw announcement data, PDF URLs). May not be needed if AKShare wrapper suffices. |
| Alembic | installed | Database migration 010 | Creates watchlist, watcher_state, and pending_disclosures tables. [VERIFIED: 9 existing migrations] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AKShare `stock_zh_a_disclosure_report_cninfo` | Direct HTTP to `cninfo.com.cn/new/hisAnnouncement/query` | AKShare wraps the same endpoint with proper headers and pagination. Direct HTTP only needed if AKShare's wrapper lacks fields (e.g., PDF download URL `adjunctUrl`). [ASSUMED] |
| Two arq cron entries (high season + off season) | Single cron with runtime month check | Two crons with `month` param could work but risk both firing during transition months. Single cron with runtime check is simpler and more predictable. |
| `stock_report_disclosure` per-stock polling | Batch poll all stocks at once | `stock_report_disclosure` returns all stocks for a period in one call (pagesize=10000). Much more efficient than per-stock. [VERIFIED: source] |

## Architecture Patterns

### System Architecture Diagram

```
[Arq Worker Process]
       |
       |-- cron_jobs:
       |     |
       |     |-- watch_disclosures (daily 09:00 / weekly Mon 09:00)
       |           |
       |           |-- 1. Read watchlist from DB (active tickers only)
       |           |-- 2. Determine current reporting period from month
       |           |-- 3. AKShare stock_report_disclosure(market, period)
       |           |     |-- ON FAILURE: AKShare stock_zh_a_disclosure_report_cninfo()
       |           |-- 4. Filter results by watchlist tickers
       |           |-- 5. Write disclosures to pending_disclosures staging table
       |           |-- 6. Enqueue process_disclosures job
       |           |-- 7. Update watcher_state table
       |
       |-- functions:
             |
             |-- process_disclosures(ctx, poll_id: str)
                   |
                   |-- 1. Read unprocessed rows from pending_disclosures
                   |-- 2. For each disclosure:
                   |     |-- Check pipeline_tasks for existing business_key
                   |     |-- If not found: NEW -> enqueue download_report(task_id)
                   |     |-- If found with later disclosure_date: AMENDMENT -> create new task
                   |     |-- If found with same date: SKIP (already processed)
                   |-- 3. Mark pending_disclosures rows as processed
                   |-- 4. Log summary

[FastAPI Process]
       |
       |-- POST /api/v1/pipeline/watchlist  (add stock)
       |-- GET  /api/v1/pipeline/watchlist  (list stocks)
       |-- DELETE /api/v1/pipeline/watchlist/{ticker}  (remove stock)
       |
       |-- Reads watchlist table for API responses
       |-- Uses existing ApiResponse[T] envelope
```

### Recommended Project Structure

```
stockvaluefinder/pipeline/
  config.py          -- Extend PipelineConfig with high_season_months, etc.
  state.py           -- (existing) PipelineState enum
  models.py          -- (existing) Add WatchlistItem, WatcherState Pydantic models
  worker.py          -- Add watch_disclosures cron, process_disclosures function
  repo.py            -- (existing) PipelineTaskRepository
  watcher.py         -- NEW: WatcherService class (poll, detect, enqueue)
  watchlist_repo.py  -- NEW: WatchlistRepository for watchlist CRUD
  watcher_repo.py    -- NEW: WatcherStateRepository for watcher_state updates

stockvaluefinder/db/models/
  watchlist.py       -- NEW: WatchlistDB ORM model
  watcher_state.py   -- NEW: WatcherStateDB ORM model
  pending_disclosure.py -- NEW: PendingDisclosureDB ORM model

stockvaluefinder/external/
  akshare_client.py  -- Add get_report_disclosures(), get_index_constituents(), get_cninfo_announcements()

stockvaluefinder/alembic/versions/
  010_watcher_tables.py -- NEW: Creates watchlist, watcher_state, pending_disclosures

stockvaluefinder/api/
  pipeline_routes.py -- Add watchlist CRUD endpoints

tests/unit/test_pipeline/
  test_watcher.py         -- WatcherService unit tests
  test_watchlist_repo.py  -- WatchlistRepository unit tests
  test_watcher_repo.py    -- WatcherStateRepository unit tests
  test_watcher_integration.py -- Integration tests
```

### Pattern 1: Season-Aware Single Cron

**What:** A single arq cron function that checks the current month against PipelineConfig.high_season_months to decide whether to poll or skip.

**When to use:** Daily cron at 09:00. On each invocation, check if current month is in high_season_months. If yes -> poll. If no and today is Monday -> poll. Otherwise -> skip.

**Example:**
```python
# Source: [VERIFIED: arq 0.25.0 cron signature + existing worker.py pattern]
from datetime import datetime, timezone

async def watch_disclosures(ctx: dict[str, Any]) -> None:
    """Cron function: poll for newly disclosed financial reports.

    Runs daily at 09:00 CST. During off-season (months not in
    high_season_months), only polls on Mondays.
    """
    config: PipelineConfig = ctx.get("config", PipelineConfig())
    now = datetime.now(timezone.utc)

    # Season check: skip if off-season and not Monday
    if now.month not in config.high_season_months and now.weekday() != 0:
        logger.debug("Off-season and not Monday, skipping poll")
        return

    watcher = ctx.get("watcher")
    if watcher is None:
        logger.error("No watcher in worker context")
        return

    try:
        result = await watcher.poll_disclosures()
        logger.info(f"Poll complete: {result.new_count} new, {result.amendment_count} amendments")
    except Exception as e:
        logger.error(f"Poll failed: {e}", exc_info=True)

# In WorkerSettings:
cron_jobs = [
    cron(
        reap_stuck_tasks,
        minute=set(range(0, 60, config.reaper_interval_minutes)),
        run_at_startup=True,
        unique=True,
        max_tries=1,
        timeout=60,
    ),
    cron(
        watch_disclosures,
        hour=9,
        minute=0,
        run_at_startup=True,
        unique=True,
        max_tries=1,
        timeout=300,  # 5 min timeout for disclosure polling
    ),
]
```

### Pattern 2: Two-Phase Poll + Process

**What:** The cron job writes raw disclosure data to a staging table (`pending_disclosures`). A separate arq job (`process_disclosures`) reads from the staging table, performs dedup against `pipeline_tasks`, and enqueues processing jobs.

**When to use:** Decouples polling (which can be retried independently) from processing (which involves business logic).

**Example:**
```python
# Staging table schema (pending_disclosures)
"""
CREATE TABLE pending_disclosures (
    disclosure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id UUID NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    report_type VARCHAR(20) NOT NULL,   -- 'annual', 'semi_annual', 'q1', 'q3'
    fiscal_year INTEGER NOT NULL,
    disclosure_date DATE,
    first_appointment DATE,
    source VARCHAR(20) NOT NULL,        -- 'akshare' or 'cninfo'
    source_raw JSONB,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX idx_pending_disclosures_poll ON pending_disclosures(poll_id);
CREATE INDEX idx_pending_disclosures_unprocessed ON pending_disclosures(processed) WHERE processed = FALSE;
"""
```

### Pattern 3: AKShare Disclosure Polling

**What:** Use AKShare `stock_report_disclosure` to batch-fetch disclosure schedules for all stocks.

**When to use:** Primary source for disclosure schedule polling.

**Example:**
```python
# Source: [VERIFIED: inspect source of akshare 1.18.46 stock_report_disclosure]
async def get_report_disclosures(
    self,
    period: str,  # e.g., "2024年报", "2024一季", "2024半年报", "2024三季"
    market: str = "沪深京",
) -> list[dict[str, Any]]:
    """Fetch disclosure schedule for all stocks in a market.

    Args:
        period: Report period in Chinese format (e.g., "2024年报").
        market: Market scope. Choices: "沪深京", "深市", "深主板",
                "创业板", "沪市", "沪主板", "科创板", "北交所".

    Returns:
        List of dicts with keys: stock_code, stock_name,
        first_appointment, actual_disclosure, first_change,
        second_change, third_change.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.stock_report_disclosure(market=market, period=period)
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

### Pattern 4: CNInfo Fallback via AKShare

**What:** Use AKShare's built-in `stock_zh_a_disclosure_report_cninfo` for per-stock CNInfo announcement data.

**When to use:** When `stock_report_disclosure` fails or returns stale data.

**Example:**
```python
# Source: [VERIFIED: inspect source of akshare 1.18.46]
async def get_cninfo_announcements(
    self,
    symbol: str,        # e.g., "000001"
    category: str = "", # e.g., "年报", "半年报", "一季报", "三季报"
    start_date: str = "",  # YYYYMMDD
    end_date: str = "",    # YYYYMMDD
) -> list[dict[str, Any]]:
    """Fetch CNInfo announcements for a specific stock.

    Args:
        symbol: 6-digit stock code.
        category: Report category filter (empty = all).
        start_date: Start date in YYYYMMDD format.
        end_date: End date in YYYYMMDD format.

    Returns:
        List of dicts with: 代码, 简称, 公告标题, 公告时间,
        announcementId, orgId.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            market="沪深京",
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

### Pattern 5: CSI 300 Constituent Lookup

**What:** Use AKShare `index_stock_cons_csindex` to get CSI 300 stock list.

**When to use:** When user wants to populate watchlist with all CSI 300 stocks (manual, not auto-seeded per D-14).

**Example:**
```python
# Source: [VERIFIED: inspect source of akshare 1.18.46]
async def get_index_constituents(
    self,
    symbol: str = "000300",  # CSI 300 index code
) -> list[dict[str, Any]]:
    """Fetch constituent stocks for a CSI index.

    Args:
        symbol: Index code (default: "000300" for CSI 300).

    Returns:
        List of dicts with: 日期, 指数代码, 指数名称,
        成分券代码 (6-digit stock code), 成分券名称, 交易所.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.index_stock_cons_csindex(symbol=symbol)
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

### Pattern 6: Watchlist CRUD API

**What:** REST endpoints for managing the watchlist following established patterns.

**When to use:** User adds/removes stocks to monitor.

**Example:**
```python
# Source: [VERIFIED: existing pipeline_routes.py + api.py patterns]
from fastapi import APIRouter, Depends
from stockvaluefinder.models.api import ApiResponse

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

@router.post("/watchlist")
async def add_to_watchlist(
    request: WatchlistAddRequest,
    ...
) -> ApiResponse[WatchlistItem]:
    """Add a stock to the watchlist."""

@router.get("/watchlist")
async def list_watchlist(
    active_only: bool = True,
    ...
) -> ApiResponse[list[WatchlistItem]]:
    """List all stocks in the watchlist."""

@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    ...
) -> ApiResponse[None]:
    """Remove a stock from the watchlist."""
```

### Anti-Patterns to Avoid

- **Two separate arq cron entries for high/off season with `month` param:** Arq does not dynamically switch cron schedules. Two crons with `month` sets could both fire during boundary months if the month calculation overlaps. Use a single cron with runtime month-check instead.
- **Polling per-stock instead of batch:** `stock_report_disclosure` returns all stocks in one call. Do NOT loop over individual stocks for the primary poll. Only use per-stock queries for CNInfo fallback.
- **Auto-seeding watchlist on startup:** D-14 explicitly states empty by default. Do not add auto-populate logic.
- **Storing raw DataFrame objects in staging table:** Always convert to dict/list before persisting. AKShare returns DataFrames that don't serialize cleanly to JSONB.
- **Using `stock_report_disclosure` with bare stock codes:** The function takes `market` + `period` parameters (Chinese labels), NOT `stock` + `period`. The market must be one of the valid choices: "沪深京", "深市", "沪市", etc. [VERIFIED: inspect source]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Disclosure schedule fetching | Custom HTTP to CNInfo | AKShare `stock_report_disclosure` | AKShare handles authentication, pagination, column normalization, and date parsing. Source verified to hit `cninfo.com.cn/new/information/getPrbookInfo` with proper params. [VERIFIED: inspect source] |
| CNInfo announcement query | Raw HTTP POST to `cninfo.com.cn/new/hisAnnouncement/query` | AKShare `stock_zh_a_disclosure_report_cninfo` | Handles stock ID mapping, category dict lookup, pagination across pages, timestamp conversion. [VERIFIED: inspect source] |
| CSI 300 constituent list | Web scraping csindex.com.cn | AKShare `index_stock_cons_csindex(symbol="000300")` | Downloads structured Excel from official URL, normalizes columns, zero-pads codes. [VERIFIED: inspect source] |
| Cron scheduling | APScheduler or custom timer | Arq `cron()` in WorkerSettings | Already established in Phase 5. Supports month, weekday, hour, minute params. `unique=True` prevents duplicate runs. [VERIFIED: installed arq 0.25.0] |
| Task deduplication | Custom dedup logic | PipelineTaskRepository.create_task() with business_key unique constraint | Existing `IntegrityError` catch on unique constraint. [VERIFIED: repo.py] |

**Key insight:** AKShare already wraps both CNInfo endpoints this phase needs. There is no need for a custom HTTP client to CNInfo for disclosure polling. The only scenario requiring direct HTTP is PDF downloading, which is Phase 7.

## Common Pitfalls

### Pitfall 1: AKShare Period Format Mismatch
**What goes wrong:** Passing period as "20241231" instead of "2024年报" to `stock_report_disclosure`.
**Why it happens:** Tushare uses date formats like "20241231", but AKShare's `stock_report_disclosure` uses Chinese period labels like "2024年报", "2024一季", "2024半年报", "2024三季".
**How to avoid:** Map report types to period strings: `{year}年报` for annual, `{year}一季` for Q1, `{year}半年报` for semi-annual, `{year}三季` for Q3. [VERIFIED: inspect source period_map]
**Warning signs:** Empty DataFrame returned from `stock_report_disclosure`.

### Pitfall 2: AKShare Rate Limiting on Batch Calls
**What goes wrong:** AKShare client gets blocked by East Money / CNInfo when making rapid sequential calls.
**Why it happens:** The existing AKShareClient has 0.5s rate limiting between calls. But `stock_report_disclosure` returns up to ~5000 rows in a single call, and CNInfo fallback per-stock could trigger many rapid requests.
**How to avoid:** Use batch `stock_report_disclosure` (one call per period) for primary source. Only fall back to per-stock CNInfo queries for specific tickers that failed in the primary poll. The existing `_run_sync` method already handles rate limiting.
**Warning signs:** `ExternalAPIError` from AKShare client with connection drop errors.

### Pitfall 3: Timezone Mismatch on Disclosure Dates
**What goes wrong:** Comparing disclosure dates across timezone boundaries produces false negatives (missed reports).
**Why it happens:** AKShare returns dates as `datetime.date` (no timezone). Pipeline tasks store timestamps as `TIMESTAMPTZ` in UTC. CST (China Standard Time, UTC+8) means a report disclosed at 2024-04-30 20:00 UTC is actually 2024-05-01 in CST.
**How to avoid:** Normalize all disclosure dates to UTC `datetime.date` before comparison. Use `datetime.now(timezone.utc)` consistently (existing pattern in repo.py).
**Warning signs:** Reports disclosed near midnight CST boundary are missed or duplicated.

### Pitfall 4: Amendment Detection Race Condition
**What goes wrong:** Two poll cycles run simultaneously and both detect the same amendment, creating duplicate tasks.
**Why it happens:** If the cron fires again before the previous poll finishes processing, both cycles could see the same amendment.
**How to avoid:** Use `unique=True` on the cron job (already default). The `pending_disclosures` staging table with poll_id grouping also isolates each cycle. PipelineTaskRepository.create_task() IntegrityError on business_key provides final safety net.
**Warning signs:** Duplicate pipeline tasks with same business_key (should be caught by unique constraint).

### Pitfall 5: Watchlist Empty Means No Polling
**What goes wrong:** Watchlist is empty by default (D-14). The watcher polls but has no tickers to filter against, resulting in zero disclosures detected.
**Why it happens:** D-14 says "empty by default -- user must explicitly add stocks via API." The watcher must handle empty watchlist gracefully.
**How to avoid:** Log a clear warning when watchlist is empty and skip the poll. Do NOT default to all CSI 300 stocks automatically.
**Warning signs:** Watcher runs successfully but creates zero tasks. No error logged.

### Pitfall 6: Arq Cron Schedule Is Static
**What goes wrong:** Expecting arq cron to dynamically switch between daily and weekly based on config changes at runtime.
**Why it happens:** Arq cron schedules are defined in WorkerSettings class attributes, evaluated once when the worker starts.
**How to avoid:** Use a single daily cron entry. The `watch_disclosures` function itself checks the current month against `PipelineConfig.high_season_months` and skips if off-season and not Monday. Config changes require worker restart (frozen dataclass pattern).
**Warning signs:** Off-season daily polls consuming unnecessary resources.

## Code Examples

### Reporting Period Calculation

```python
# Source: [VERIFIED: akshare 1.18.46 stock_report_disclosure source]
def get_current_report_periods(now: datetime) -> list[tuple[str, str, int]]:
    """Calculate which report periods to poll based on current month.

    Returns list of (period_str, report_type, fiscal_year) tuples.
    Example: ("2024年报", "annual", 2024)

    Annual reports (年报): Due Apr 30. Poll Jan-Apr.
    Q1 reports (一季报): Due Apr 30. Poll Jan-Apr.
    Semi-annual reports (半年报): Due Aug 31. Poll Jul-Aug.
    Q3 reports (三季报): Due Oct 31. Poll Oct-Nov.
    """
    year = now.year
    month = now.month
    periods = []

    if month <= 4:
        # Annual + Q1 reporting season
        periods.append((f"{year - 1}年报", "annual", year - 1))
        periods.append((f"{year}一季", "q1", year))
    elif month <= 8:
        # Semi-annual reporting season
        periods.append((f"{year}半年报", "semi_annual", year))
    elif month <= 11:
        # Q3 reporting season
        periods.append((f"{year}三季", "q3", year))
    else:
        # Dec: early annual reports may appear
        periods.append((f"{year - 1}年报", "annual", year - 1))

    return periods
```

### Ticker Code Normalization

```python
# Source: [VERIFIED: existing eastmoney_hsf10_symbol + akshare source]
def normalize_akshare_ticker(raw_code: str, exchange: str = "") -> str:
    """Convert AKShare stock code to project ticker format.

    AKShare returns bare 6-digit codes like '600519', '000001'.
    Project format requires '600519.SH', '000001.SZ'.

    Args:
        raw_code: 6-digit stock code from AKShare.
        exchange: Exchange name from AKShare (if available).

    Returns:
        Normalized ticker string.
    """
    code = str(raw_code).strip().zfill(6)
    if exchange and "上海" in exchange:
        return f"{code}.SH"
    if exchange and "深圳" in exchange:
        return f"{code}.SZ"
    # Fallback: infer from code prefix
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    return f"{code}.SZ"  # Default to SZ for unknown
```

### Business Key Construction

```python
# Source: [VERIFIED: existing PipelineTaskCreate.business_key pattern]
def build_business_key(ticker: str, fiscal_year: int, report_type: str) -> str:
    """Construct business_key for pipeline task deduplication.

    Format: ticker:fiscal_year:report_type
    Example: '600519.SH:2023:annual'

    Args:
        ticker: Normalized stock ticker (e.g., '600519.SH').
        fiscal_year: Fiscal year of the report.
        report_type: Report type ('annual', 'semi_annual', 'q1', 'q3').

    Returns:
        Business key string.
    """
    return f"{ticker}:{fiscal_year}:{report_type}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-stock disclosure query | Batch `stock_report_disclosure` for all stocks | AKShare always supported batch | One API call vs ~5000; use batch always |
| Direct CNInfo HTTP scraping | AKShare `stock_zh_a_disclosure_report_cninfo` wrapper | AKShare 1.14+ | Handles auth, pagination, column normalization |
| APScheduler for cron | Arq `cron_jobs` in WorkerSettings | Phase 5 decision | One system for both task queue and scheduling |
| Two cron entries for season switching | Single cron with runtime month check | This phase (D-09) | Simpler, avoids boundary conflicts |

**Deprecated/outdated:**
- `stock_report_disclosure` with `stock` parameter: The installed version (1.18.46) uses `market` + `period` parameters, not `stock`. Some older documentation references a `stock` param but that is from a different version or function. [VERIFIED: inspect signature]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CNInfo direct HTTP only needed for PDF download (Phase 7), not for disclosure schedule checking | Don't Hand-Roll | If AKShare's `stock_zh_a_disclosure_report_cninfo` wrapper lacks necessary fields (e.g., PDF URL), may need direct HTTP earlier |
| A2 | `stock_report_disclosure` returns all stocks in one call with pagesize=10000, sufficient for CSI 300 universe | Pattern 3 | If pagesize limit causes truncation, need pagination logic |
| A3 | Arq 0.25.0 `cron()` with `unique=True` prevents concurrent runs even if previous poll takes longer than 24 hours | Pattern 1 | If unique behavior differs from expected, could get concurrent polls |
| A4 | AKShare `index_stock_cons_csindex` returns current CSI 300 constituents (not historical) | Pattern 5 | If it returns historical data, may need date filtering |

## Open Questions

1. **Should `pending_disclosures` be included in migration 010?**
   - What we know: D-11 specifies a staging table. D-17 specifies migration 010 for watchlist + watcher_state. The staging table is part of the two-phase architecture.
   - What's unclear: Whether D-17 intentionally excludes it or assumes it.
   - Recommendation: Include it in migration 010. It's a Phase 6 table and keeping all Phase 6 schema changes in one migration is cleaner.

2. **How to handle ticker format mismatch between AKShare and project?**
   - What we know: AKShare `stock_report_disclosure` returns bare 6-digit codes in `股票代码` column. Project uses `600519.SH` format.
   - What's unclear: Whether `index_stock_cons_csindex` includes exchange info in `交易所` column.
   - Recommendation: Use `交易所` column from `index_stock_cons_csindex` when populating watchlist. For `stock_report_disclosure`, infer exchange from code prefix (6xx -> SH, 0xx/3xx -> SZ).

3. **What happens when `stock_report_disclosure` returns NaT for `实际披露`?**
   - What we know: The `实际披露` column contains the actual disclosure date. Companies that haven't disclosed yet show NaT.
   - What's unclear: Whether to store NaT rows in staging table or filter them out during poll.
   - Recommendation: Filter out NaT rows during poll -- only stage disclosures with an actual disclosure date. Undisclosed reports are not actionable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | arq job queue | Needs check (no redis-cli) | -- | Start Redis via Docker |
| PostgreSQL (port 5433) | Pipeline tables | Needs check (no pg_isready) | -- | Start PostgreSQL via Docker |
| Python 3.12+ | Runtime | Available | 3.12.11 | -- |
| arq | Worker process | Available (in venv) | 0.25.0 | -- |
| AKShare | Data source | Available (in venv) | 1.18.46 | -- |
| arq CLI | Worker management | Available | 0.25.0 | -- |
| FastAPI | API server | Available (in venv) | -- | -- |

**Missing dependencies with no fallback:**
- Redis and PostgreSQL must be running for integration tests. Unit tests use mocks.

**Missing dependencies with fallback:**
- None -- all code-level dependencies are installed in the project venv.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | pyproject.toml (tool.pytest) |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_pipeline/ -x -q` |
| Full suite command | `cd stockvaluefinder && uv run pytest --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WATCH-01 | Poll disclosure schedules via AKShare | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_poll_disclosures -x` | Wave 0 |
| WATCH-01 | Cron job fires at configured time | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_watch_disclosures_cron -x` | Wave 0 |
| WATCH-02 | Detect new vs existing disclosures | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_detect_new_reports -x` | Wave 0 |
| WATCH-02 | Detect amendments via disclosure_date comparison | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_detect_amendments -x` | Wave 0 |
| WATCH-03 | Season-aware scheduling (high season daily, off-season weekly) | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_season_aware_scheduling -x` | Wave 0 |
| WATCH-03 | PipelineConfig.high_season_months validation | unit | `uv run pytest tests/unit/test_pipeline/test_config.py::test_high_season_months -x` | Wave 0 (extend existing) |
| WATCH-04 | Watchlist CRUD via API | integration | `uv run pytest tests/unit/test_pipeline/test_watchlist_api.py -x` | Wave 0 |
| WATCH-04 | CSI 300 constituent lookup | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_get_index_constituents -x` | Wave 0 |
| WATCH-05 | Enqueue arq job for new disclosure | unit | `uv run pytest tests/unit/test_pipeline/test_watcher.py::test_enqueue_new_disclosure -x` | Wave 0 |
| WATCH-05 | PipelineTaskRepository.create_task dedup | unit | `uv run pytest tests/unit/test_pipeline/test_pipeline_repo.py -x` | Existing (Phase 5) |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_pipeline/ -x -q`
- **Per wave merge:** `cd stockvaluefinder && uv run pytest --cov=stockvaluefinder/pipeline --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_pipeline/test_watcher.py` -- WatcherService tests (poll, detect, enqueue)
- [ ] `tests/unit/test_pipeline/test_watchlist_repo.py` -- WatchlistRepository tests
- [ ] `tests/unit/test_pipeline/test_watcher_repo.py` -- WatcherStateRepository tests
- [ ] `tests/unit/test_pipeline/test_watchlist_api.py` -- Watchlist API endpoint tests
- [ ] Extend `tests/unit/test_pipeline/test_config.py` -- Add tests for new PipelineConfig fields
- [ ] Extend `tests/unit/test_pipeline/test_worker.py` -- Add tests for watch_disclosures cron
- [ ] `tests/unit/test_pipeline/test_orm_models.py` -- Add tests for new ORM models (watchlist, watcher_state, pending_disclosure)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user system, no auth (deferred per Out of Scope) |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No auth, single user |
| V5 Input Validation | yes | Pydantic models with Field validators for watchlist endpoints (ticker regex, name length) |
| V6 Cryptography | no | No crypto needed in this phase |

### Known Threat Patterns for FastAPI + External Data

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ticker injection in watchlist API | Tampering | Pydantic Field pattern validation `r"^\d{4,6}\.(SH|SZ|HK)$"` (existing pattern from PipelineTaskCreate) |
| AKShare response data poisoning | Tampering | Validate AKShare response structure before processing; catch KeyError on expected columns |
| CNInfo rate-limiting / blocking | Denial of Service | Existing AKShareClient retry with exponential backoff; rate limiting (0.5s between calls) |
| SQL injection via ticker | Tampering | SQLAlchemy parameterized queries (existing pattern in PipelineTaskRepository) |

## Sources

### Primary (HIGH confidence)
- AKShare 1.18.46 installed version -- `inspect.signature()` and `inspect.getsource()` verified for `stock_report_disclosure`, `index_stock_cons_csindex`, `stock_zh_a_disclosure_report_cninfo`
- arq 0.25.0 installed version -- `inspect.signature()` verified for `cron()`, `CronJob` dataclass fields, `ArqRedis.enqueue_job()`
- Existing codebase: config.py, worker.py, repo.py, pipeline_routes.py, akshare_client.py, api.py -- all read and verified

### Secondary (MEDIUM confidence)
- AKShare Context7 docs (/akfamily/akshare) -- confirmed function parameters and response formats match installed version
- arq Context7 docs (/python-arq/arq and /websites/arq-docs_helpmanual_io) -- confirmed cron API and WorkerSettings patterns
- Web search results for CNInfo API endpoint (rate-limited, but confirmed by AKShare source code inspection)

### Tertiary (LOW confidence)
- CNInfo direct HTTP endpoint details (`/new/hisAnnouncement/query`) -- confirmed by reading AKShare wrapper source, but direct HTTP usage not needed in this phase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already installed and verified via inspect
- Architecture: HIGH -- two-phase pattern well-established, arq cron API verified
- AKShare API parameters: HIGH -- function signatures verified from installed package source code
- CNInfo fallback: HIGH -- AKShare wrapper source inspected, same underlying endpoint
- Pitfalls: HIGH -- based on verified API behaviors and existing codebase patterns
- Season-aware scheduling: MEDIUM -- runtime month-check approach is sound but not battle-tested in this codebase

**Research date:** 2026-05-01
**Valid until:** 2026-05-31 (stable stack, AKShare may update)
