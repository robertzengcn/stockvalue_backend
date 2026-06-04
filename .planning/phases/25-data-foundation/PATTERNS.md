# Phase 25: Data Foundation - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 13 (new/modified)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `stockvaluefinder/db/models/index_constituent.py` | model (ORM) | CRUD | `stockvaluefinder/db/models/alpha.py` (AlphaScoreDB) | exact |
| `stockvaluefinder/db/models/market_scan_run.py` | model (ORM) | state-machine | `stockvaluefinder/db/models/pipeline_task.py` (PipelineTaskDB) | exact |
| `stockvaluefinder/db/models/market_scan_candidate.py` | model (ORM) | CRUD | `stockvaluefinder/db/models/risk.py` (RiskScoreDB) | exact |
| `stockvaluefinder/db/models/market_scan_rule.py` | model (ORM) | CRUD | `stockvaluefinder/db/models/policy.py` (PolicyDocumentDB) | role-match |
| `stockvaluefinder/models/market_scan.py` | model (Pydantic) | request-response | `stockvaluefinder/models/alpha.py` (AlphaRequest/AlphaAnalysisResult) | exact |
| `stockvaluefinder/models/market_scan.py` (Create/Update) | model (Pydantic) | CRUD | `stockvaluefinder/models/alpha.py` (AlphaScoreCreate/AlphaScoreUpdate) | exact |
| `stockvaluefinder/repositories/index_constituent_repo.py` | repository | CRUD | `stockvaluefinder/repositories/alpha_repo.py` (AlphaScoreRepository) | exact |
| `stockvaluefinder/repositories/market_scan_run_repo.py` | repository | CRUD | `stockvaluefinder/repositories/risk_repo.py` (RiskScoreRepository) | exact |
| `stockvaluefinder/repositories/market_scan_candidate_repo.py` | repository | CRUD | `stockvaluefinder/repositories/risk_repo.py` (RiskScoreRepository) | exact |
| `stockvaluefinder/repositories/market_scan_rule_repo.py` | repository | CRUD | `stockvaluefinder/repositories/alpha_repo.py` (AlphaScoreRepository) | role-match |
| `stockvaluefinder/config.py` (MarketScannerConfig addition) | config | batch | `stockvaluefinder/config.py` (AlphaConfig, PolicyResonanceConfig) | exact |
| `stockvaluefinder/alembic/versions/020_market_scanner_tables.py` | migration | batch | `stockvaluefinder/alembic/versions/014_alpha_scores_table.py` | exact |
| `tests/unit/test_repositories/test_market_scan_repos.py` | test | CRUD | `tests/unit/test_repositories/test_policy_repo.py` | exact |

## Pattern Assignments

---

### `stockvaluefinder/db/models/index_constituent.py` (model/ORM, CRUD)

**Analog:** `stockvaluefinder/db/models/alpha.py` (AlphaScoreDB, lines 14-145)

This is a reference-data table mapping tickers to index membership (e.g., CSI 300 constituents). It needs a composite unique constraint on (index_code, ticker) like AlphaScoreDB has on (ticker, fiscal_year).

**Imports pattern** (from alpha.py, lines 1-11):
```python
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base
```

**UUID PK + UniqueConstraint pattern** (from alpha.py, lines 26-36):
```python
__tablename__ = "alpha_scores"

__table_args__ = (
    UniqueConstraint("ticker", "fiscal_year", name="uq_alpha_ticker_fiscal_year"),
)

# Primary key
analysis_id: Mapped[str] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
    comment="Unique identifier",
)
```

**FK to stocks pattern** (from alpha.py, lines 39-45):
```python
ticker: Mapped[str] = mapped_column(
    String(20),
    ForeignKey("stocks.ticker"),
    nullable=False,
    index=True,
    comment="Stock code (foreign key)",
)
```

**Deviations for scanner:**
- No fiscal_year column; instead, need `index_code` (String, e.g., "000300.SH" for CSI 300), `weight` (Float for index weight), `date_added` (Date for when constituent was added).
- UniqueConstraint on (index_code, ticker) to prevent duplicate membership rows.

---

### `stockvaluefinder/db/models/market_scan_run.py` (model/ORM, state-machine)

**Analog:** `stockvaluefinder/db/models/pipeline_task.py` (PipelineTaskDB, lines 14-127)

This tracks a scan run lifecycle: PENDING -> RUNNING -> COMPLETED / FAILED. Very close to PipelineTaskDB state machine pattern.

**State machine pattern** (from pipeline_task.py, lines 62-68):
```python
state: Mapped[str] = mapped_column(
    String(20),
    nullable=False,
    default="pending",
    index=True,
    comment="Current pipeline state (pending, downloading, parsing, analyzing, done, failed)",
)
```

**Retry tracking** (from pipeline_task.py, lines 77-89):
```python
retry_count: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=0,
    comment="Number of retry attempts",
)

max_retries: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=3,
    comment="Maximum allowed retries",
)
```

**Timestamp pattern** (from pipeline_task.py, lines 106-119):
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=lambda: datetime.now(timezone.utc),
    comment="Task creation timestamp (UTC)",
)

updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
    comment="Last update timestamp (UTC)",
)
```

**Deviations for scanner:**
- No ticker FK (a scan run processes the entire index, not a single stock).
- Need `index_code` (String), `total_constituents` (Integer), `passed_count` (Integer), `failed_count` (Integer).
- `error_message` (Text, nullable) for failure details.
- `rules_applied` (JSONB) storing the snapshot of rule definitions used in this run.
- `result_summary` (JSONB, nullable) for aggregate results.

---

### `stockvaluefinder/db/models/market_scan_candidate.py` (model/ORM, CRUD)

**Analog:** `stockvaluefinder/db/models/risk.py` (RiskScoreDB, lines 24-179)

Each row is a single stock evaluation within a scan run, with pass/fail results for each rule. Similar to how RiskScoreDB stores per-stock risk analysis results.

**UUID PK + dual FK pattern** (from risk.py, lines 30-52):
```python
score_id: Mapped[str] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
    comment="Unique identifier",
)

# Foreign keys
ticker: Mapped[str] = mapped_column(
    String(20),
    ForeignKey("stocks.ticker"),
    nullable=False,
    index=True,
    comment="Stock code (foreign key)",
)

report_id: Mapped[str] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("financial_reports.report_id"),
    nullable=False,
    unique=True,
    comment="Reference to FinancialReport",
)
```

**JSONB structured data pattern** (from risk.py, lines 77-81):
```python
mscore_data: Mapped[dict[str, Any]] = mapped_column(
    JSONB,
    nullable=False,
    comment="M-Score component data (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA)",
)
```

**Deviations for scanner:**
- FK to `market_scan_runs.run_id` instead of `financial_reports.report_id`.
- Need `passed` (Boolean) for overall pass/fail.
- `rule_results` (JSONB) storing per-rule pass/fail details and scores.
- `composite_score` (Float) for overall ranking score.
- No unique constraint on run_id -- multiple candidates per run.
- Composite index on (run_id, ticker) for fast lookup.

---

### `stockvaluefinder/db/models/market_scan_rule.py` (model/ORM, CRUD)

**Analog:** `stockvaluefinder/db/models/policy.py` (PolicyDocumentDB -- config/reference data pattern)

Reference data table storing rule definitions for the scanner. Simple CRUD with a unique name constraint.

**Pattern to follow** (UUID PK + String columns + JSONB):
```python
rule_id: Mapped[str] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
    comment="Unique identifier",
)

rule_name: Mapped[str] = mapped_column(
    String(100),
    nullable=False,
    unique=True,
    comment="Human-readable rule name",
)

rule_type: Mapped[str] = mapped_column(
    String(50),
    nullable=False,
    index=True,
    comment="Rule category (risk, valuation, yield, composite)",
)

is_active: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=True,
    comment="Whether rule is currently active",
)

parameters: Mapped[dict[str, Any]] = mapped_column(
    JSONB,
    nullable=False,
    default=dict,
    comment="Rule parameters (thresholds, weights, etc.)",
)
```

---

### `stockvaluefinder/models/market_scan.py` (model/Pydantic, request-response + CRUD)

**Analog:** `stockvaluefinder/models/alpha.py` (AlphaRequest, AlphaAnalysisResult, AlphaScoreCreate, AlphaScoreUpdate)

**Request model pattern** (from alpha.py, lines 67-88):
```python
class AlphaRequest(BaseModel):
    """Request model for Alpha composite score analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., 600519.SH)",
    )
    year: int | None = Field(None, ge=2000, le=2099)

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "600519.SH", "year": 2023},
            ]
        }
```

**Result model (frozen) pattern** (from alpha.py, lines 91-129):
```python
class AlphaAnalysisResult(BaseModel):
    """Complete Alpha composite score analysis result."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code")
    fiscal_year: int = Field(..., description="Fiscal year of analysis")
    component_scores: AlphaComponentScores = Field(...)
    alpha_score: float = Field(..., ge=0.0, le=100.0)
    audit_trail: dict[str, Any] = Field(
        default_factory=dict, description="Calculation audit trail"
    )
    calculated_at: datetime = Field(..., description="Timestamp of calculation")
```

**Create model pattern** (from alpha.py, lines 132-170):
```python
class AlphaScoreCreate(BaseModel):
    """Model for creating an Alpha score in the database."""

    analysis_id: UUID
    ticker: str
    fiscal_year: int
    # ... flat fields matching ORM columns
```

**Update model pattern** (from alpha.py, lines 173-185):
```python
class AlphaScoreUpdate(BaseModel):
    """Model for updating an Alpha score. All fields optional."""

    alpha_score: float | None = None
    audit_trail: dict[str, Any] | None = None
```

**Models to create in this file:**
1. `MarketScanRequest` -- index_code, rules (optional override), max_candidates
2. `MarketScanRunResult` -- frozen result model with run metadata
3. `MarketScanCandidateResult` -- frozen per-stock result with rule_results
4. `ScanRuleDefinition` -- rule config definition (frozen)
5. `MarketScanRunCreate` -- persistence model for runs
6. `MarketScanCandidateCreate` -- persistence model for candidates
7. `MarketScanRuleCreate` -- persistence model for rules
8. `MarketScanRunUpdate` -- partial update for runs (state transitions)
9. `MarketScanCandidateUpdate` -- partial update for candidates

---

### `stockvaluefinder/repositories/index_constituent_repo.py` (repository, CRUD)

**Analog:** `stockvaluefinder/repositories/alpha_repo.py` (AlphaScoreRepository, lines 14-134)

**Upsert-by-composite-key pattern** (from alpha_repo.py, lines 32-89):
```python
async def upsert_by_ticker_year(
    self,
    data: AlphaScoreCreate,
) -> AlphaScoreDB:
    stmt = select(AlphaScoreDB).where(
        AlphaScoreDB.ticker == data.ticker,
        AlphaScoreDB.fiscal_year == data.fiscal_year,
    )
    result = await self._session.execute(stmt)
    existing = result.scalar_one_or_none()

    field_values = dict(
        ticker=data.ticker,
        fiscal_year=data.fiscal_year,
        # ...
    )

    if existing is not None:
        for field, value in field_values.items():
            setattr(existing, field, value)
        await self._session.flush()
        await self._session.refresh(existing)
        return existing

    db_obj = AlphaScoreDB(
        analysis_id=data.analysis_id,
        **field_values,
    )
    self._session.add(db_obj)
    await self._session.flush()
    await self._session.refresh(db_obj)
    return db_obj
```

**Query pattern** (from alpha_repo.py, lines 112-133):
```python
async def get_by_ticker(
    self,
    ticker: str,
    limit: int = 10,
) -> list[AlphaScoreDB]:
    stmt = (
        select(AlphaScoreDB)
        .where(AlphaScoreDB.ticker == ticker)
        .order_by(AlphaScoreDB.fiscal_year.desc())
        .limit(limit)
    )
    result = await self._session.execute(stmt)
    return list(result.scalars().all())
```

**Key methods needed:**
- `upsert_by_index_ticker` -- insert/update constituent by (index_code, ticker)
- `get_by_index_code` -- all constituents for a given index
- `get_by_ticker` -- all index memberships for a given ticker
- `bulk_upsert` -- batch refresh of entire index constituent list

---

### `stockvaluefinder/repositories/market_scan_run_repo.py` (repository, CRUD)

**Analog:** `stockvaluefinder/repositories/risk_repo.py` (RiskScoreRepository, lines 15-384)

**Inheritance + init pattern** (from risk_repo.py, lines 15-22):
```python
class RiskScoreRepository(
    BaseRepository[RiskScoreDB, RiskScoreCreate, RiskScoreUpdate]
):
    """Repository for RiskScore data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RiskScoreDB, session)
```

**Custom create pattern** (from risk_repo.py, lines 229-277):
```python
async def create(
    self,
    data: RiskScoreCreate,
) -> RiskScoreDB:
    db_obj = RiskScoreDB(
        score_id=data.score_id,
        ticker=data.ticker,
        # ... map each field explicitly
    )
    self._session.add(db_obj)
    await self._session.flush()
    await self._session.refresh(db_obj)
    return db_obj
```

**Key methods needed:**
- `get_by_run_id` -- single run by PK
- `get_latest_run` -- most recent run for a given index_code
- `get_by_state` -- all runs in a given state (pending, running, etc.)
- `update_state` -- transition state machine

---

### `stockvaluefinder/repositories/market_scan_candidate_repo.py` (repository, CRUD)

**Analog:** `stockvaluefinder/repositories/risk_repo.py` (RiskScoreRepository)

**Key methods needed:**
- `get_by_run_id` -- all candidates for a given scan run
- `get_passed_candidates` -- candidates that passed all rules in a run
- `get_by_ticker_run` -- candidate for a specific (run_id, ticker) pair
- `create` -- insert candidate with rule results

---

### `stockvaluefinder/config.py` -- MarketScannerConfig addition (config, batch)

**Analog:** `stockvaluefinder/config.py` (AlphaConfig lines 254-271, PolicyResonanceConfig lines 187-219)

**Frozen dataclass config pattern** (from config.py, lines 254-271):
```python
@dataclass(frozen=True)
class AlphaConfig:
    """Configuration for Alpha composite score analysis."""

    ROIC_WACC_WEIGHT: float = 0.40
    CAPITAL_ALLOCATION_WEIGHT: float = 0.30
    POLICY_WEIGHT: float = 0.20
    MOAT_WEIGHT: float = 0.10

    SPREAD_CLAMP_MIN: float = -0.10
    SPREAD_CLAMP_MAX: float = 0.10
```

**AppConfig integration pattern** (from config.py, lines 296-329):
```python
@dataclass(frozen=True)
class AppConfig:
    valuation: ValuationConfig
    risk: RiskConfig
    # ... existing fields
    alpha: AlphaConfig
    auth: AuthConfig

    @classmethod
    @lru_cache
    def get_instance(cls) -> "AppConfig":
        return cls(
            # ... existing fields
            alpha=AlphaConfig(),
            auth=AuthConfig(),
        )
```

**Global singleton + __all__ export** (from config.py, lines 332-373):
```python
alpha_config = AlphaConfig()

__all__ = [
    # ... existing
    "AlphaConfig",
    "alpha_config",
]
```

**MarketScannerConfig fields to define:**
```python
@dataclass(frozen=True)
class MarketScannerConfig:
    DEFAULT_INDEX_CODE: str = "000300.SH"  # CSI 300
    MAX_CANDIDATES_DEFAULT: int = 50
    CACHE_TTL_SECONDS: int = 3600  # 1 hour for scan results
```

**Changes to AppConfig:** Add `market_scanner: MarketScannerConfig` field, instantiate in `get_instance()`, add to `__all__`, add global `market_scanner_config = MarketScannerConfig()`.

---

### `stockvaluefinder/alembic/versions/020_market_scanner_tables.py` (migration, batch)

**Analog:** `stockvaluefinder/alembic/versions/014_alpha_scores_table.py` (lines 1-153) and `stockvaluefinder/alembic/versions/009_pipeline_tables.py` (multi-table migration)

**Migration header pattern** (from 014, lines 8-20):
```python
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**UUID PK + FK + JSONB pattern** (from 014, lines 27-43):
```python
op.create_table(
    "alpha_scores",
    sa.Column(
        "analysis_id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        comment="Unique identifier",
    ),
    sa.Column(
        "ticker",
        sa.String(20),
        sa.ForeignKey("stocks.ticker"),
        nullable=False,
        comment="Stock code (foreign key)",
    ),
```

**JSONB with server_default** (from 014, lines 111-115):
```python
sa.Column(
    "weights_used",
    postgresql.JSONB(),
    nullable=False,
    server_default="{}",
    comment="Weight configuration used",
),
```

**Index creation** (from 014, lines 134-148):
```python
op.create_index(
    "ix_alpha_scores_ticker",
    "alpha_scores",
    ["ticker"],
)
```

**Multi-table downgrade ordering** (from 009, lines 165-168):
```python
def downgrade() -> None:
    # Drop tables in reverse dependency order (FKs)
    op.drop_table("market_scan_candidates")
    op.drop_table("market_scan_runs")
    op.drop_table("market_scan_rules")
    op.drop_table("index_constituents")
```

**Table creation order (respecting FKs):**
1. `index_constituents` (no FK to scanner tables)
2. `market_scan_rules` (no FK to scanner tables)
3. `market_scan_runs` (standalone or FK to index_constituents)
4. `market_scan_candidates` (FK to market_scan_runs, FK to stocks)

---

### `tests/unit/test_repositories/test_market_scan_repos.py` (test, CRUD)

**Analog:** `tests/unit/test_repositories/test_policy_repo.py` (lines 1-199)

**Mock session helper** (from test_policy_repo.py, lines 20-28):
```python
def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session
```

**Test fixture pattern** (from test_policy_repo.py, lines 58-59):
```python
@pytest.mark.asyncio
class TestPolicyDocumentRepository:
    async def test_get_by_document_id_found(self):
        session = _make_mock_session()
        # ... setup mock_result
        repo = PolicyDocumentRepository(session)
        result = await repo.get_by_document_id(doc.document_id)
        assert result is not None
```

**Test structure to follow:**
- One test class per repository (TestIndexConstituentRepository, TestMarketScanRunRepository, TestMarketScanCandidateRepository, TestMarketScanRuleRepository)
- Test found / not_found for get_by_id methods
- Test create with field mapping verification
- Test upsert (insert new + update existing) for IndexConstituentRepository
- Test state transitions for MarketScanRunRepository

---

## Shared Patterns

### UUID Primary Key Convention
**Source:** All ORM models (`stockvaluefinder/db/models/*.py`)
**Apply to:** All 4 new ORM models

```python
from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

# Primary key pattern used in every table:
entity_id: Mapped[str] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid4,
    comment="Unique identifier",
)
```

Convention: PK column named `{entity}_id` (e.g., `run_id`, `candidate_id`, `rule_id`). Exception: `index_constituents` could use `constituent_id`.

### Foreign Key to stocks.ticker
**Source:** `stockvaluefinder/db/models/alpha.py` lines 39-45, `stockvaluefinder/db/models/risk.py` lines 38-44
**Apply to:** index_constituents, market_scan_candidates

```python
ticker: Mapped[str] = mapped_column(
    String(20),
    ForeignKey("stocks.ticker"),
    nullable=False,
    index=True,
    comment="Stock code (foreign key)",
)
```

### Timestamps (timezone-aware UTC)
**Source:** `stockvaluefinder/db/models/pipeline_task.py` lines 106-119
**Apply to:** market_scan_runs, market_scan_rules (not index_constituents which is reference data)

```python
from datetime import datetime, timezone

created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=lambda: datetime.now(timezone.utc),
    comment="... timestamp (UTC)",
)

updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
    comment="Last update timestamp (UTC)",
)
```

### JSONB for Semi-Structured Data
**Source:** `stockvaluefinder/db/models/risk.py` lines 77-81, `stockvaluefinder/db/models/alpha.py` lines 118-123
**Apply to:** All scanner models storing variable data (rule_results, rules_applied, parameters)

```python
from sqlalchemy.dialects.postgresql import JSONB

data_field: Mapped[dict[str, Any]] = mapped_column(
    JSONB,
    nullable=False,
    default=dict,
    comment="Description of JSON structure",
)
```

### Repository Base Class Inheritance
**Source:** `stockvaluefinder/repositories/base.py` lines 16-119
**Apply to:** All 4 new repositories

```python
from stockvaluefinder.repositories.base import BaseRepository

class XxxRepository(
    BaseRepository[XxxDB, XxxCreate, XxxUpdate]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(XxxDB, session)
```

Provides: `get_by_id`, `get_all`, `create` (generic), `update`, `delete`. Override `create` and `update` when field mapping is needed (e.g., enum-to-string conversion).

### Pydantic Model Layering (Base / Create / Update / Result)
**Source:** `stockvaluefinder/models/alpha.py`
**Apply to:** All scanner Pydantic models

Convention:
- `{Domain}Base` -- shared fields
- `{Domain}Create` -- full fields for repository create (includes PK)
- `{Domain}Update` -- all optional for partial updates
- `{Domain}Result` -- frozen, complete model for API responses

### db/models/__init__.py Registration
**Source:** `stockvaluefinder/db/models/__init__.py` lines 1-47
**Apply to:** Must add 4 new imports when creating ORM models

```python
from stockvaluefinder.db.models.index_constituent import IndexConstituentDB
from stockvaluefinder.db.models.market_scan_run import MarketScanRunDB
from stockvaluefinder.db.models.market_scan_candidate import MarketScanCandidateDB
from stockvaluefinder.db.models.market_scan_rule import MarketScanRuleDB
```

Add to `__all__` list as well.

### Enum Pattern (StrEnum)
**Source:** `stockvaluefinder/models/enums.py` lines 20-27, 71-78
**Apply to:** New enums for scan states and rule types

```python
class ScanState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanRuleType(str, Enum):
    RISK = "risk"
    VALUATION = "valuation"
    YIELD = "yield"
    COMPOSITE = "composite"
```

Add these to `stockvaluefinder/models/enums.py`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All patterns have strong analogs in existing codebase |

The market scanner module introduces no fundamentally new patterns. Every component (state machine, CRUD, reference data, config dataclass, migration) has a direct precedent in the codebase.

## Metadata

**Analog search scope:**
- `stockvaluefinder/stockvaluefinder/db/models/` (22 ORM models)
- `stockvaluefinder/stockvaluefinder/models/` (20 Pydantic model files)
- `stockvaluefinder/stockvaluefinder/repositories/` (17 repository files)
- `stockvaluefinder/stockvaluefinder/config.py` (10 config dataclasses)
- `stockvaluefinder/alembic/versions/` (19 migration files)
- `stockvaluefinder/tests/unit/test_repositories/` (1 test file)

**Files scanned:** 79
**Pattern extraction date:** 2026-06-04
