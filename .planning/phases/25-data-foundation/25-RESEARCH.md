# Phase 25: Data Foundation - Research

**Researched:** 2026-06-04
**Domain:** PostgreSQL schema design, AKShare index data, SQLAlchemy 2.0 async ORM, frozen config validation
**Confidence:** HIGH

## Summary

Phase 25 establishes the data persistence layer for the Market Index Value Scanner. This covers four requirements: index constituent sync with AKShare (IDX-01), constituent history tracking with removal dates (IDX-02), scan run lifecycle state machine (EXE-04), and configurable screening thresholds via frozen dataclass (SCR-04).

The AKShare `index_stock_cons_csindex` function is already available in the existing `AKShareClient` and returns constituent lists for CSI 300 (symbol `000300`) and CSI 500 (symbol `000905`) with Chinese column names, a date column indicating effective date, and stock codes/names. The project already has a well-established pattern for UUID PKs using `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)` with `default=uuid4`, frozen dataclass configs with `__post_init__` validation, and a generic `BaseRepository` pattern with async SQLAlchemy sessions.

**Primary recommendation:** Follow the exact existing patterns for ORM models (UUID PKs, JSONB for flexible fields, timezone-aware datetimes), frozen config (PipelineConfig as the template), and repository inheritance (risk_repo.py as the most complete example with upsert).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IDX-01 | Index constituent sync (CSI 300/500 from AKShare, effective dates, history) | `ak.index_stock_cons_csindex` verified; columns: 日期, 指数代码, 成分券代码, 成分券名称; existing `AKShareClient.get_index_constituents` method already wraps it |
| IDX-02 | Constituent history tracking (removal dates, last-known-good on failure) | `index_constituents` table with `effective_date`, `removed_date`, `is_active` fields; `deactivate_missing` repository method design in tech doc section 4.3 |
| EXE-04 | Scan run lifecycle (pending/running/completed/partial_failed, counts, error summary) | `market_scan_runs` table with status enum, count fields, JSONB error_summary; state machine in tech doc section 7.1 |
| SCR-04 | Configurable screening thresholds (frozen dataclass config) | `PipelineConfig` in `stockvaluefinder/pipeline/config.py` is the exact pattern to follow; `MarketScannerConfig` design in tech doc section 13 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Index constituent data fetching | API / Backend | External (AKShare) | Backend orchestrates the sync; AKShare provides the raw data |
| Constituent history persistence | Database / Storage | -- | PostgreSQL owns the history tracking with effective/removed dates |
| Scan run state machine | Database / Storage | API / Backend | DB persists run status; backend orchestrates transitions |
| Configurable thresholds | API / Backend | -- | Frozen dataclass in application code, no DB dependency for config |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.47 | Async ORM, migrations | [VERIFIED: project venv] Already in use project-wide |
| Alembic | 1.18.4 | Database migrations | [VERIFIED: project venv] 19 existing migrations |
| Pydantic | 2.12.5 | Domain model validation | [VERIFIED: project venv] All domain models use it |
| asyncpg | 0.31.0 | PostgreSQL async driver | [VERIFIED: project venv] Production driver for SQLAlchemy async |
| AKShare | 1.18.46 | Index constituent data | [VERIFIED: project venv] Already has `get_index_constituents` method |
| pytest | 9.0+ | Testing | [VERIFIED: project venv] Test framework for all phases |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | installed | Async test support | All repository and service tests |
| pytest-mock | 3.15+ | Mocking external calls | AKShare sync tests |

**No new dependencies required for this phase.** Everything is already installed.

## Architecture Patterns

### System Architecture Diagram

```
AKShare API (index_stock_cons_csindex)
    |
    v
AKShareClient.get_index_constituents()  [existing, line 499-523]
    |
    v
IndexConstituentRepository  [NEW]
    |-- upsert_constituents(index_code, constituents, effective_date)
    |-- get_active_by_index(index_code)
    |-- deactivate_missing(index_code, active_tickers, removed_date)
    |
    v
PostgreSQL: index_constituents table  [NEW]

Manual/Cron Trigger
    |
    v
MarketScannerService.run_scan()  [Phase 27, not this phase]
    |
    v
MarketScanRunRepository  [NEW]
    |-- create_run(data) -> run (status=pending)
    |-- mark_running(run_id) -> run (status=running)
    |-- mark_completed(run_id, counts) -> run (status=completed)
    |-- mark_partial_failed(run_id, error_summary) -> run (status=partial_failed)
    |
    v
PostgreSQL: market_scan_runs table  [NEW]
PostgreSQL: market_scan_candidates table  [NEW]

MarketScannerConfig  [NEW, frozen dataclass]
    |-- index_codes, daily_top_n, min_margin_of_safety, etc.
    |-- __post_init__ validation (follows PipelineConfig pattern)
```

### Recommended Project Structure

```
stockvaluefinder/
  db/models/
    index_constituent.py     # NEW: IndexConstituentDB ORM model
    market_scan.py            # NEW: MarketScanRunDB, MarketScanCandidateDB, MarketScanRulesDB
  models/
    market_scanner.py         # NEW: Pydantic models for scanner domain
    enums.py                  # MODIFY: add ScanType, ScanStatus, IndexCode enums
  repositories/
    index_constituent_repo.py # NEW: IndexConstituentRepository
    market_scan_repo.py       # NEW: MarketScanRunRepository, MarketScanCandidateRepository
  market_scanner/
    __init__.py               # NEW
    config.py                 # NEW: MarketScannerConfig frozen dataclass
    errors.py                 # NEW: ScannerError hierarchy
  alembic/versions/
    020_market_scanner_tables.py  # NEW: migration for 3 tables
```

### Pattern 1: UUID Primary Key in SQLAlchemy 2.0

**What:** All new tables use UUID PKs following the existing convention.
**When to use:** Every new ORM model in this phase.

```python
# Source: [VERIFIED: stockvaluefinder/db/models/risk.py line 30-35]
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class MyModelDB(Base):
    __tablename__ = "my_table"

    my_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )
```

Key details from existing codebase:
- `Mapped[str]` is used even though the column stores UUIDs, because `UUID(as_uuid=True)` handles the conversion [VERIFIED: risk.py line 30, valuation.py line 20]
- `default=uuid4` generates UUIDs client-side, no DB round-trip needed
- The Alembic migration uses `sa.dialects.postgresql.UUID(as_uuid=True)` for column definition [VERIFIED: 019_rate_limit_overrides_table.py]

### Pattern 2: Frozen Dataclass Config with Validation

**What:** Config classes use `@dataclass(frozen=True)` with `__post_init__` validation.
**When to use:** `MarketScannerConfig` for SCR-04.

```python
# Source: [VERIFIED: stockvaluefinder/pipeline/config.py]
@dataclass(frozen=True)
class MarketScannerConfig:
    """Configuration for market scanner thresholds and weights."""

    index_codes: tuple[str, ...] = ("CSI300", "CSI500")
    rules_version: str = "v1"
    daily_top_n: int = 50
    weekly_top_n: int = 100
    min_margin_of_safety: float = 0.30
    min_composite_score: float = 60.0
    deep_analysis_concurrency: int = 5
    request_delay_seconds: float = 0.5
    max_price_cache_age_minutes: int = 30
    alpha_max_age_days: int = 30

    def __post_init__(self) -> None:
        if not self.index_codes:
            raise ValueError("index_codes must not be empty")
        if self.daily_top_n <= 0:
            raise ValueError(f"daily_top_n must be > 0, got {self.daily_top_n}")
        if self.weekly_top_n < self.daily_top_n:
            raise ValueError(
                f"weekly_top_n ({self.weekly_top_n}) must be >= daily_top_n ({self.daily_top_n})"
            )
        if not (0 <= self.min_margin_of_safety <= 1):
            raise ValueError(
                f"min_margin_of_safety must be in [0, 1], got {self.min_margin_of_safety}"
            )
        if not (0 <= self.min_composite_score <= 100):
            raise ValueError(
                f"min_composite_score must be in [0, 100], got {self.min_composite_score}"
            )
        if self.deep_analysis_concurrency < 1:
            raise ValueError(
                f"deep_analysis_concurrency must be >= 1, got {self.deep_analysis_concurrency}"
            )
```

### Pattern 3: Repository with Domain-Specific Methods

**What:** Repositories extend `BaseRepository` with typed domain methods.
**When to use:** All new repositories.

```python
# Source: [VERIFIED: stockvaluefinder/repositories/risk_repo.py pattern]
from stockvaluefinder.repositories.base import BaseRepository

class IndexConstituentRepository(
    BaseRepository[IndexConstituentDB, IndexConstituentCreate, IndexConstituentUpdate]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(IndexConstituentDB, session)

    async def get_active_by_index(self, index_code: str) -> list[IndexConstituentDB]:
        stmt = (
            select(IndexConstituentDB)
            .where(
                IndexConstituentDB.index_code == index_code,
                IndexConstituentDB.is_active.is_(True),
            )
            .order_by(IndexConstituentDB.ticker)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_missing(
        self, index_code: str, active_tickers: set[str], removed_date: date
    ) -> int:
        """Set is_active=False and removed_date for constituents no longer in the index."""
        stmt = (
            update(IndexConstituentDB)
            .where(
                IndexConstituentDB.index_code == index_code,
                IndexConstituentDB.is_active.is_(True),
                IndexConstituentDB.ticker.notin_(active_tickers),
            )
            .values(is_active=False, removed_date=removed_date)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
```

### Pattern 4: Scan Run State Machine

**What:** Scan runs transition through a defined state sequence with atomic updates.
**When to use:** `MarketScanRunRepository` methods.

State transitions:
```
pending --> running --> completed
                   \-> partial_failed
                   \-> failed  (future, not in Phase 25 scope)
```

```python
# Each transition is a repository method that validates current state
async def mark_running(self, run_id: UUID) -> MarketScanRunDB:
    stmt = select(MarketScanRunDB).where(MarketScanRunDB.run_id == run_id)
    result = await self._session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status != "pending":
        raise ValueError(f"Run {run_id} is {run.status}, expected pending")
    run.status = "running"
    run.started_at = datetime.now(tz=timezone.utc)
    await self._session.flush()
    await self._session.refresh(run)
    return run
```

### Anti-Patterns to Avoid

- **String-typed status fields without enum enforcement:** Use `StrEnum` (see `models/enums.py`) for ScanType and ScanStatus, but store as string in DB (matching existing pattern for RiskLevel, ValuationLevel).
- **Mutable config classes:** All config classes MUST be `frozen=True`. Never allow `setter` methods on config.
- **Skipping `__post_init__` validation:** Invalid configs should fail at instantiation time, not at runtime. PipelineConfig shows the exact pattern.
- **Using bare `datetime.utcnow()`:** Existing codebase has a mix of `datetime.utcnow` (old, stock.py) and `datetime.now(timezone.utc)` (newer, risk.py, valuation.py). New code MUST use `datetime.now(timezone.utc)` for timezone-aware timestamps.
- **Putting index_code validation only in Pydantic:** The ORM model and the config should also constrain valid index codes. Use the frozen config's `index_codes` tuple as the source of truth.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UUID generation | Custom UUID factory | `uuid.uuid4` (already project standard) | Already used in 10+ models |
| Async DB session | Custom connection pool | `async_session_maker` from `db.base.py` | Already configured with pool_size=5, max_overflow=10 |
| Base repository CRUD | New CRUD from scratch | `BaseRepository` generic class | Already provides get_by_id, get_all, create, update, delete |
| Index constituent fetching | Web scraping CSI index site | `AKShareClient.get_index_constituents` | Already implemented at line 499, uses `ak.index_stock_cons_csindex` |
| Config validation | Manual if/else chains in business logic | Frozen dataclass `__post_init__` | Already established in PipelineConfig |
| JSON field storage | Separate columns for each scan metric | `JSONB` columns (screening_snapshot, reasons, risk_flags, error_summary) | Flexible, queryable, follows existing pattern in risk.py and valuation.py |

**Key insight:** The existing codebase already has 19 Alembic migrations, 17 ORM models, 17 repositories, and 5 frozen config classes. Every piece of infrastructure needed for this phase exists. The task is pure schema definition and glue code following established patterns.

## Common Pitfalls

### Pitfall 1: AKShare Returns Chinese Column Names

**What goes wrong:** `index_stock_cons_csindex` returns columns named `日期`, `指数代码`, `成分券代码`, `成分券名称`, not English names.
**Why it happens:** AKShare wraps Chinese financial data sources and preserves their naming.
**How to avoid:** Map columns explicitly in the sync service:
- `日期` -> `effective_date`
- `指数代码` -> `index_code` (maps to "CSI300" or "CSI500", not "000300")
- `成分券代码` -> `ticker` (needs `.SH`/`.SZ` suffix appended based on 交易所 column)
- `成分券名称` -> `name`

**Warning signs:** If ticker codes are stored without market suffix (e.g., `000001` instead of `000001.SZ`), they won't match existing FK references in the `stocks` table.

### Pitfall 2: Ticker Code Format Mismatch

**What goes wrong:** AKShare returns bare 6-digit codes (`000001`, `600519`), but the project uses suffixed codes (`000001.SZ`, `600519.SH`).
**Why it happens:** Different data sources use different formats.
**How to avoid:** Use the existing `eastmoney_hsf10_symbol` function (in akshare_client.py) as reference for the mapping logic, or derive suffix from the `交易所` column: "深圳证券交易所" -> `.SZ`, "上海证券交易所" -> `.SH`.
**Warning signs:** FK constraint violations when inserting constituents that reference `stocks.ticker`.

### Pitfall 3: Scan Status Race Conditions

**What goes wrong:** Two concurrent scan runs for the same index could both be in "running" state.
**Why it happens:** No unique constraint on (index_code, status) and async operations.
**How to avoid:** Don't add a uniqueness constraint on status -- instead, the service layer should check for existing running scans before creating a new one. The repository `create_run` method should accept `index_codes` as JSONB (not a single index), and the service should prevent duplicate runs.
**Warning signs:** Two "running" scans for the same index appearing in the database.

### Pitfall 4: Frozen Dataclass With Mutable Defaults

**What goes wrong:** Using `list` or `dict` as default values in frozen dataclasses causes `ValueError` at instantiation.
**Why it happens:** Python mutable defaults in dataclasses require `field(default_factory=...)`.
**How to avoid:** Use `tuple` for sequences (e.g., `index_codes: tuple[str, ...] = ("CSI300", "CSI500")`) and `frozenset` for sets. This is already the established pattern in PipelineConfig.
**Warning signs:** `mutable default <class 'list'> for field ...` error at class definition time.

### Pitfall 5: Missing Effective Date From AKShare

**What goes wrong:** Assuming the effective date is always today, but AKShare actually returns a `日期` column that may differ.
**Why it happens:** The index constituent list may have been updated on a previous day if you're syncing on a weekend or holiday.
**How to avoid:** Always read the `日期` column from the API response rather than using `date.today()`. The effective_date should come from the data source.
**Warning signs:** All constituents have the same effective_date even across syncs that happened on different actual dates.

## Code Examples

### AKShare Index Constituent Response Format

Verified live output from `ak.index_stock_cons_csindex(symbol='000300')`:

```
Columns: ['日期', '指数代码', '指数名称', '指数英文名称', '成分券代码', '成分券名称', '成分券英文名称', '交易所', '交易所英文名称']
Shape: (300, 9)
Sample row:
  日期=2026-06-03, 指数代码=000300, 成分券代码=000001, 成分券名称=平安银行,
  交易所=深圳证券交易所
```

For CSI 500 (`symbol='000905'`):
```
Shape: (500, 9)
Same columns, same format.
```

### Existing `get_index_constituents` Method

```python
# Source: [VERIFIED: stockvaluefinder/external/akshare_client.py lines 499-523]
async def get_index_constituents(
    self,
    symbol: str = "000300",
) -> list[dict[str, Any]]:
    """Fetch constituent stocks for a CSI index."""
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.index_stock_cons_csindex(symbol=symbol)
        if df is None or df.empty:
            return []
        return df.to_dict("records")
    return await self._run_sync(_fetch)
```

### Ticker Code Mapping Pattern

```python
# Source: [VERIFIED: stockvaluefinder/external/akshare_client.py lines 16-39]
# The eastmoney_hsf10_symbol function shows the mapping convention:
# SH prefix -> .SH suffix (Shanghai)
# SZ prefix -> .SZ suffix (Shenzhen)

# For index constituents, derive from 交易所 column:
EXCHANGE_TO_SUFFIX = {
    "上海证券交易所": ".SH",
    "深圳证券交易所": ".SZ",
}

def normalize_ticker(raw_code: str, exchange: str) -> str:
    """Convert AKShare raw code + exchange to project ticker format."""
    suffix = EXCHANGE_TO_SUFFIX.get(exchange, "")
    return f"{raw_code}{suffix}"
```

### Alembic Migration Pattern

```python
# Source: [VERIFIED: stockvaluefinder/alembic/versions/019_rate_limit_overrides_table.py]
revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"

def upgrade() -> None:
    op.create_table(
        "index_constituents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("index_code", sa.String(20), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("removed_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_raw", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("index_code", "ticker", "effective_date", name="uq_index_ticker_date"),
    )
    op.create_index("ix_index_constituents_code_active", "index_constituents", ["index_code", "is_active"])
    op.create_index("ix_index_constituents_ticker_active", "index_constituents", ["ticker", "is_active"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `datetime.utcnow()` (naive) | `datetime.now(timezone.utc)` (aware) | Gradual migration in codebase | New models MUST use timezone-aware; old models untouched |
| `Optional[X]` type hints | `X \| None` (Python 3.10+) | Python 3.12 adoption | All new code uses pipe syntax |
| Single PK per table (autoincrement) | UUID PKs with `uuid4` default | Since initial schema | All new tables use UUID PKs |
| Config in .env only | Frozen dataclass + `__post_init__` | Since v1.1 (PipelineConfig) | All configs validated at import time |

**Deprecated/outdated:**
- `datetime.utcnow()` is deprecated in Python 3.12. Use `datetime.now(timezone.utc)` instead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `index_constituents.ticker` does NOT need a FK to `stocks.ticker` because constituent sync may run before stock records exist | DB Schema | If FK is required, constituent sync will fail when a stock hasn't been inserted into `stocks` table yet. The tech design does not specify a FK on this column. |
| A2 | The `market_scan_rules` table (section 4.6 of tech doc) should be included in Phase 25 since the tech design puts all tables in Phase 1 | Scope | If deferred, Phase 26 needs its own migration for the rules table. Including it now avoids a second migration later. |
| A3 | `market_scan_candidates` table is needed in Phase 25 (for FK from runs) even though candidates are populated in later phases | DB Schema | If deferred, Phase 27 needs its own migration. But the tech design puts all tables in Phase 1. |

## Open Questions

1. **Should `index_constituents.ticker` have a FK to `stocks.ticker`?**
   - What we know: The tech design (section 4.3) does not show a FK. The `stocks` table may not have all 800 CSI 300+500 tickers pre-loaded.
   - What's unclear: Whether constituent sync should also ensure stock records exist.
   - Recommendation: Do NOT add FK for Phase 25. The sync service can call `ensure_stock_exists` (existing helper in `api/stock_helpers.py`) during sync if needed, but that belongs in Phase 27 service orchestration, not the data layer.

2. **Should the `market_scan_rules` table be included in Phase 25?**
   - What we know: Tech design section 4.6 defines it. Tech design section 15 puts it in Phase 1 (database and domain models).
   - What's unclear: Whether rules persistence is needed before the screening engine (Phase 26) uses them.
   - Recommendation: Include it in Phase 25 migration since it's in the tech design's Phase 1 scope and the `market_scan_runs.rules_version` references it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All DB operations | Unknown (check DATABASE_URL) | -- | N/A |
| AKShare | IDX-01 constituent sync | Yes | 1.18.46 | -- |
| SQLAlchemy | ORM layer | Yes | 2.0.47 | -- |
| Alembic | Migrations | Yes | 1.18.4 | -- |
| pytest | Testing | Yes | 9.0+ | -- |
| uv | Package management | Yes | -- | -- |

**Missing dependencies with no fallback:** None identified.

**Missing dependencies with fallback:** None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | tests/conftest.py (existing, minimal) |
| Quick run command | `uv run pytest tests/unit/test_market_scanner/ -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IDX-01 | Sync CSI 300/500 constituents from AKShare | unit | `uv run pytest tests/unit/test_market_scanner/test_repositories.py -q` | No, Wave 0 |
| IDX-01 | Store effective_date from AKShare response | unit | Same as above | No, Wave 0 |
| IDX-02 | Mark removed constituents with removal date | unit | Same as above | No, Wave 0 |
| IDX-02 | Preserve last-known-good on sync failure | unit | `uv run pytest tests/unit/test_market_scanner/test_service.py -q` | No, Wave 0 |
| EXE-04 | Create run with pending status | unit | `uv run pytest tests/unit/test_market_scanner/test_repositories.py -q` | No, Wave 0 |
| EXE-04 | Transition pending -> running | unit | Same as above | No, Wave 0 |
| EXE-04 | Transition running -> completed | unit | Same as above | No, Wave 0 |
| EXE-04 | Transition running -> partial_failed | unit | Same as above | No, Wave 0 |
| EXE-04 | Record total/screened/candidate counts | unit | Same as above | No, Wave 0 |
| EXE-04 | Store error_summary JSONB | unit | Same as above | No, Wave 0 |
| SCR-04 | Config rejects invalid values | unit | `uv run pytest tests/unit/test_market_scanner/test_config.py -q` | No, Wave 0 |
| SCR-04 | Config accepts valid values with defaults | unit | Same as above | No, Wave 0 |
| SCR-04 | No hardcoded thresholds in business logic | manual | Code review | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_market_scanner/ -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_market_scanner/__init__.py` -- test package init
- [ ] `tests/unit/test_market_scanner/test_config.py` -- covers SCR-04 (MarketScannerConfig validation)
- [ ] `tests/unit/test_market_scanner/test_models.py` -- covers Pydantic model validation
- [ ] `tests/unit/test_market_scanner/test_repositories.py` -- covers IDX-01, IDX-02, EXE-04
- [ ] Shared fixture: mock AKShare constituent data factory (can go in conftest.py)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 25 is data layer only, no auth endpoints |
| V3 Session Management | no | No sessions in this phase |
| V4 Access Control | no | No access control in data layer |
| V5 Input Validation | yes | Pydantic models validate all input; frozen dataclass validates config |
| V6 Cryptography | no | No sensitive data in this phase |

### Known Threat Patterns for Python/FastAPI + PostgreSQL

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via raw queries | Tampering | SQLAlchemy parameterized queries (used throughout) |
| Mass assignment via Pydantic | Tampering | Frozen Pydantic models, explicit field definitions |
| Config tampering | Tampering | Frozen dataclass, validated at import time |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: project venv] SQLAlchemy 2.0.47, Alembic 1.18.4, Pydantic 2.12.5, AKShare 1.18.46
- [VERIFIED: stockvaluefinder/external/akshare_client.py] `get_index_constituents` method at line 499-523, uses `ak.index_stock_cons_csindex`
- [VERIFIED: live API test] `ak.index_stock_cons_csindex(symbol='000300')` returns 300 rows, `symbol='000905'` returns 500 rows, with Chinese column names including `日期`, `成分券代码`, `成分券名称`, `交易所`
- [VERIFIED: stockvaluefinder/db/models/risk.py] UUID PK pattern with `UUID(as_uuid=True)`, `default=uuid4`
- [VERIFIED: stockvaluefinder/pipeline/config.py] Frozen dataclass with `__post_init__` validation (PipelineConfig)
- [VERIFIED: stockvaluefinder/repositories/risk_repo.py] Full repository pattern with upsert, typed methods
- [VERIFIED: stockvaluefinder/repositories/base.py] Generic BaseRepository with CRUD operations
- [VERIFIED: stockvaluefinder/alembic/versions/019_rate_limit_overrides_table.py] Migration pattern

### Secondary (MEDIUM confidence)
- [CITED: doc/market_index_value_scanner_technical_design.md sections 4, 6, 7, 13] Database schema, repository design, service design, config design

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified in project venv, no new dependencies
- Architecture: HIGH - follows 19 existing migrations and 17 existing models as templates
- AKShare API: HIGH - live tested `index_stock_cons_csindex` for both CSI 300 and CSI 500
- Pitfalls: HIGH - verified column names and ticker format mismatches via live API testing
- Config pattern: HIGH - PipelineConfig provides exact template with validation

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable stack, no fast-moving dependencies)
