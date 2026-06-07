# Phase 31: Persistence & API Integration - Research

**Researched:** 2026-06-07
**Domain:** SQLAlchemy ORM, Alembic migrations, FastAPI route extension, LLM narrative prompts
**Confidence:** HIGH

## Summary

Phase 31 integrates the pledge risk calculation (Phase 30 output: `PledgeRiskAnalyzer.analyze()` producing `PledgeRiskResult`) into the existing risk analysis pipeline by adding database persistence, extending the risk API endpoint, and updating the narrative prompt. This is an integration phase -- the heavy lifting (data fetching, risk calculation) is done. The work is primarily: (1) create two new ORM models and an Alembic migration, (2) write a pledge repository with upsert/replace-all semantics, (3) extend the risk route to call pledge analysis and persist results, (4) extend the narrative prompt with guarded pledge data sections.

The codebase has clear, consistent patterns for every one of these tasks. Migration 020 shows the table-creation pattern. Migration 006/007 shows the add-column-to-risk_scores pattern. `RiskScoreRepository` shows the upsert pattern. `risk_routes.py` shows the API flow. `narrative_prompts.py` shows the prompt builder pattern. The planner can follow these patterns directly.

**Primary recommendation:** Follow the existing patterns mechanically -- no new paradigms needed. The risk is in getting the integration flow right (pledge data fetch -> analysis -> persistence -> narrative) with correct graceful degradation at each step.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Two separate new tables (equity_pledge_snapshots, equity_pledge_details) store raw pledge data from AKShare. Plus nullable JSONB columns (pledge_risk, risk_level_breakdown) on existing risk_scores table for computed PledgeRiskResult from Phase 30's PledgeRiskAnalyzer. Clean separation: raw data history vs analysis output.
- **D-02:** Pledge risk is embedded in the existing POST /analyze/risk response. New request parameter include_pledge_risk=true (default). Response gains pledge_risk object and risk_level_breakdown fields. No separate endpoint. Single API call returns everything. Matches API-01/API-02/API-03.
- **D-03:** Single Alembic migration 021 creates both new pledge tables AND adds nullable JSONB columns to risk_scores. Existing rows naturally get NULL values (standard nullable column behavior). Atomic and simple.
- **D-04:** Extend existing build_risk_prompt() in narrative_prompts.py with a pledge risk paragraph section. Include guardrails: only use data from structured pledge_risk fields (NARR-02), no fabrication of pledge numbers, state "pledge data unavailable" when missing without implying low risk (NARR-03), omit closeout distance when safety_margin is null (NARR-04). Single LLM call.

### Claude's Discretion
- Exact ORM model field types and column definitions (follow existing RiskScoreDB pattern)
- Repository method signatures and upsert/replace-all logic (follow existing BaseRepository pattern)
- Response model structure for pledge_risk object in API response
- Alembic migration file naming and structure (follow existing migration pattern)
- Narrative prompt text and guardrail phrasing
- Error handling for pledge data fetch failures within the risk API flow

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | Persist company pledge snapshots with unique constraint on (ticker, latest_date, source) | New EquityPledgeSnapshotDB ORM model, migration 021 creates table with UniqueConstraint |
| DB-02 | Persist shareholder pledge details with indexes on (ticker, announcement_date) and (ticker, holder_name) | New EquityPledgeDetailDB ORM model, migration 021 creates table with composite indexes |
| DB-03 | Extend risk_scores with pledge_risk JSONB and risk_level_breakdown JSONB, both nullable | Migration 021 adds two JSONB columns following migration 006/007 pattern; RiskScoreDB ORM model updated |
| DB-04 | Preserve raw API response in source_raw JSONB field for audit traceability | Both new tables include source_raw JSONB column (matches index_constituents pattern in migration 020) |
| DB-05 | Upsert for snapshots, replace-all for details per ticker | PledgeSnapshotRepository.upsert_by_ticker_date_source() and replace_details_for_ticker() methods |
| DB-06 | Alembic migration 021 creates tables and extends risk_scores without modifying existing data | Single migration file, revision "021", down_revision "020", nullable columns only |
| API-01 | include_pledge_risk=true (default) request parameter | Extend RiskAnalysisRequest with include_pledge_risk: bool = True |
| API-02 | Response includes pledge_risk object with risk_level, ratios, red_flags, data_quality | Extend RiskScore/RiskScoreWithNarrative or add PledgeRiskResponseModel |
| API-03 | Response includes risk_level_breakdown with financial/pledge/final levels and merge_reason | Already modeled as RiskLevelBreakdown in equity_pledge.py from Phase 30 |
| API-04 | Graceful degradation: pledge fails -> financial results still return, pledge_risk shows UNAVAILABLE | Try/except around pledge fetch in risk_routes.py, PledgeRiskResult with UNAVAILABLE data_quality |
| API-05 | HK stocks return pledge_risk.supported=false without error | is_hk_ticker() check before pledge fetch, return PledgeRiskResult(supported=False) |
| NARR-01 | Risk narrative includes equity pledge paragraph when data available | Extend build_risk_prompt() with pledge_data parameter and pledge section |
| NARR-02 | Prompt explicitly forbids generating pledge numbers not in structured fields | Add guardrail instruction in prompt: "DO NOT generate any pledge numbers not present in the data" |
| NARR-03 | Data unavailable -> state "pledge data unavailable" without implying low risk | Conditional prompt section: when pledge_risk is None, insert explicit instruction |
| NARR-04 | closeout_safety_margin null -> omit closeout distance mention | Conditional instruction in prompt: "If closeout_safety_margin is null, do NOT mention closeout distance" |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pledge data persistence | API / Backend | Database | Route handler orchestrates fetch + persist; DB stores raw and computed data |
| Pledge risk computation | API / Backend | -- | PledgeRiskAnalyzer.analyze() is sync pure function (Phase 30) |
| Risk API extension | API / Backend | -- | Existing risk_routes.py adds pledge flow step |
| Narrative generation | API / Backend | -- | NarrativeService + extended prompt template |
| Graceful degradation | API / Backend | -- | Try/except in route, pledge failures must not break financial risk |
| Migration schema changes | Database | -- | Alembic migration 021 |

## Standard Stack

### Core (all already installed, verified)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.47 | ORM for pledge tables | Project standard for all DB models [VERIFIED: codebase] |
| Alembic | 1.18.4 | Migration 021 | Project standard for schema changes [VERIFIED: codebase] |
| Pydantic | 2.12.5 | Domain models for request/response | Project standard, frozen=True pattern [VERIFIED: codebase] |
| FastAPI | 0.133.1 | Route extension | Existing risk_routes.py [VERIFIED: codebase] |
| asyncpg | 0.31.0 | PostgreSQL async driver | Already in use via get_db() [VERIFIED: codebase] |

### No new packages needed

This phase uses only existing project dependencies. No `pip install` required.

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project dependencies (SQLAlchemy, Alembic, Pydantic, FastAPI). Audit is not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
RiskAnalysisRequest (include_pledge_risk=true)
    |
    v
[risk_routes.py analyze_risk()]
    |
    +---> ExternalDataService.get_financial_report() --> RiskAnalyzer.analyze() --> financial_risk_score
    |
    +---> [if include_pledge_risk AND !HK]
    |       |
    |       +---> ExternalDataService.get_equity_pledge_snapshot(ticker)
    |       +---> ExternalDataService.get_equity_pledge_details(ticker)
    |       |
    |       +---> PledgeRiskAnalyzer.analyze(ticker, snapshot, details, financial_risk_level, red_flags)
    |       |         |
    |       |         +---> PledgeRiskResult (company_risk, holder_risk, closeout_risk, breakdown, red_flags)
    |       |
    |       +---> PledgeSnapshotRepository.upsert(snapshot, raw_payload)
    |       +---> PledgeDetailRepository.replace_all(ticker, details)
    |       +---> merge_risk_levels(financial, pledge) --> final_risk_level
    |
    +---> [graceful degradation: pledge failures caught, UNAVAILABLE result]
    |
    +---> build_risk_prompt(ticker, result_data_with_pledge) --> NarrativeService.generate_narrative()
    |
    +---> RiskScoreRepository.upsert_by_report_id(risk_create_with_pledge_fields)
    |
    v
ApiResponse[RiskScoreWithNarrative] (with pledge_risk + risk_level_breakdown)
```

### Recommended Project Structure (new files only)

```
stockvaluefinder/stockvaluefinder/
    db/models/
        equity_pledge.py              # NEW: EquityPledgeSnapshotDB, EquityPledgeDetailDB
    repositories/
        equity_pledge_repo.py         # NEW: PledgeSnapshotRepository, PledgeDetailRepository
    alembic/versions/
        021_equity_pledge_tables.py   # NEW: Migration 021
```

Files to modify (existing):
```
stockvaluefinder/stockvaluefinder/
    db/models/__init__.py             # Register new ORM models
    db/models/risk.py                 # Add pledge_risk, risk_level_breakdown columns
    models/risk.py                    # Add pledge_risk, risk_level_breakdown to RiskScore/RiskScoreCreate
    models/narrative.py               # Extend RiskScoreWithNarrative with pledge fields
    api/risk_routes.py                # Add include_pledge_risk param, pledge fetch + persist flow
    services/narrative_prompts.py     # Extend build_risk_prompt with pledge section
    repositories/risk_repo.py         # Add pledge_risk/risk_level_breakdown to create/upsert
```

### Pattern 1: ORM Model with JSONB, unique constraint, and indexes

**What:** New ORM models for pledge tables following RiskScoreDB and IndexConstituentDB patterns.
**When to use:** Plan 31-01 (ORM models).

```python
# Source: stockvaluefinder/db/models/risk.py + stockvaluefinder/db/models/index_constituent.py patterns
from sqlalchemy import String, Float, Integer, Date, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

class EquityPledgeSnapshotDB(Base):
    """ORM model for company pledge snapshots."""
    __tablename__ = "equity_pledge_snapshots"

    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker"), nullable=False, index=True,
    )
    latest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    company_pledge_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ... other fields from tech design section 7.2 ...
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("ticker", "latest_date", "source", name="uq_pledge_snapshot_ticker_date_src"),
    )
```

### Pattern 2: Repository with upsert and replace-all

**What:** Pledge repositories with upsert for snapshots (match by unique constraint) and delete+insert for details.
**When to use:** Plan 31-01 (repositories).

```python
# Source: stockvaluefinder/repositories/risk_repo.py upsert_by_report_id pattern
class PledgeSnapshotRepository(BaseRepository[EquityPledgeSnapshotDB, ..., ...]):
    async def upsert_by_ticker_date_source(
        self, data: EquityPledgeSnapshotCreate,
    ) -> EquityPledgeSnapshotDB:
        stmt = select(EquityPledgeSnapshotDB).where(
            EquityPledgeSnapshotDB.ticker == data.ticker,
            EquityPledgeSnapshotDB.latest_date == data.latest_date,
            EquityPledgeSnapshotDB.source == data.source,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            for field, value in field_values.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        # else create new
        ...

class PledgeDetailRepository(BaseRepository[EquityPledgeDetailDB, ..., ...]):
    async def replace_details_for_ticker(
        self, ticker: str, details: list[EquityPledgeDetailCreate],
    ) -> list[EquityPledgeDetailDB]:
        # Delete all existing details for this ticker
        stmt = delete(EquityPledgeDetailDB).where(
            EquityPledgeDetailDB.ticker == ticker,
        )
        await self._session.execute(stmt)
        # Insert new details
        created = []
        for detail_data in details:
            db_obj = EquityPledgeDetailDB(**detail_data.model_dump())
            self._session.add(db_obj)
            created.append(db_obj)
        await self._session.flush()
        return created
```

### Pattern 3: Adding nullable JSONB columns to risk_scores

**What:** Migration 021 adds pledge_risk and risk_level_breakdown JSONB columns following migration 006/007 patterns.
**When to use:** Plan 31-01 (migration).

```python
# Source: stockvaluefinder/alembic/versions/006_add_narrative_columns.py
def upgrade() -> None:
    op.add_column(
        "risk_scores",
        sa.Column(
            "pledge_risk",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Pledge risk analysis result (JSON)",
        ),
    )
    op.add_column(
        "risk_scores",
        sa.Column(
            "risk_level_breakdown",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Financial vs pledge risk merge breakdown",
        ),
    )
```

### Pattern 4: Graceful degradation in risk route

**What:** Pledge data fetch wrapped in try/except; failures produce UNAVAILABLE result without breaking financial risk.
**When to use:** Plan 31-02 (API integration).

```python
# Source: stockvaluefinder/api/risk_routes.py existing pattern + tech design section 13.4
pledge_risk_result = None
if request.include_pledge_risk:
    try:
        # Check HK first (RISK-09)
        if not risk_score.ticker.endswith(".HK"):
            snapshot = await data_service.get_equity_pledge_snapshot(ticker)
            details = await data_service.get_equity_pledge_details(ticker)

            pledge_analyzer = PledgeRiskAnalyzer()
            pledge_risk_result = pledge_analyzer.analyze(
                ticker=ticker,
                snapshot=snapshot,
                details=details,
                financial_risk_level=risk_score.risk_level,
                financial_red_flags=risk_score.red_flags,
            )

            # Persist pledge data (within same transaction)
            pledge_snapshot_repo = PledgeSnapshotRepository(db)
            pledge_detail_repo = PledgeDetailRepository(db)
            if snapshot is not None:
                await pledge_snapshot_repo.upsert_by_ticker_date_source(snapshot)
            if details:
                await pledge_detail_repo.replace_details_for_ticker(ticker, details)
        else:
            # HK tickers: return unsupported result
            pledge_risk_result = PledgeRiskAnalyzer().analyze(
                ticker=ticker,
                snapshot=None,
                details=[],
                financial_risk_level=risk_score.risk_level,
                financial_red_flags=risk_score.red_flags,
            )
    except Exception:
        logger.warning(f"Pledge risk analysis failed for {ticker}", exc_info=True)
        pledge_risk_result = None  # Narrative will handle missing data

# Update risk_level if pledge upgraded it
final_risk_level = risk_score.risk_level
if pledge_risk_result and pledge_risk_result.risk_level_breakdown:
    final_risk_level = pledge_risk_result.risk_level_breakdown.final_risk_level
```

### Pattern 5: Narrative prompt extension with guardrails

**What:** Extend build_risk_prompt() with conditional pledge data section and explicit guardrails.
**When to use:** Plan 31-03 (narrative).

```python
# Source: stockvaluefinder/services/narrative_prompts.py build_risk_prompt pattern
def build_risk_prompt(
    ticker: str,
    result_data: dict[str, Any],
    pledge_data: dict[str, Any] | None = None,
) -> tuple[str, str]:
    pledge_section = ""
    if pledge_data is not None:
        if pledge_data.get("data_quality", {}).get("freshness") == "UNAVAILABLE":
            pledge_section = """
7. 股权质押风险数据不可得（请注意：不可得不代表低风险，请勿暗示质押风险较低）
   - 请明确说明"质押数据不可得"
"""
        else:
            margin_note = ""
            if pledge_data.get("closeout_safety_margin") is not None:
                margin_note = f"   - 平仓线安全距离: {pledge_data['closeout_safety_margin']:.1f}%\n"
            pledge_section = f"""
7. 股权质押风险分析:
   - 风险等级: {pledge_data.get('risk_level_breakdown', {}).get('final_risk_level', 'N/A')}
   - 公司质押比例: {pledge_data.get('company_pledge_ratio')}
   - 控股股东质押比例: {pledge_data.get('controlling_holder_pledge_ratio')}
{margin_note}
   重要约束：
   - 你只能使用以上结构化字段中的质押数值，不得编造任何质押相关数字
   - 如果closeout_safety_margin为null，请勿提及平仓线距离
"""
    # Append pledge_section to user_prompt ...
```

### Anti-Patterns to Avoid

- **Breaking the financial risk pipeline:** Pledge failures must NEVER prevent M-Score/F-Score from being returned. Wrap ALL pledge logic in try/except at the route level.
- **Mutating RiskScore in place:** RiskScore is frozen=True. Use model_copy(update={...}) or construct a new result dict for the response.
- **Creating a separate pledge endpoint:** CONTEXT.md D-02 explicitly locks: single endpoint, pledge data embedded in risk response.
- **Forgetting HK ticker check before pledge fetch:** Must check is_hk_ticker() before calling data_service pledge methods. HK tickers skip pledge entirely.
- **Using server_default for nullable JSONB columns:** Migrations 006/007 show nullable columns should be added WITHOUT server_default for nullable JSONB (just nullable=True). Migration 007 used server_default only for non-nullable columns.
- **Updating RiskScoreDB.orm in-place in the upsert:** The upsert_by_report_id pattern does setattr for each field. New pledge_risk and risk_level_breakdown fields must be added to the field_values dict in the upsert method.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Upsert logic | Custom INSERT ON CONFLICT SQL | SQLAlchemy select + update-or-insert pattern (existing in risk_repo.py) | Consistent with codebase, handles async session correctly |
| Risk level merge | Custom comparison logic | merge_risk_levels() from pledge_risk_service.py | Already built and tested in Phase 30 |
| Pledge risk grading | New threshold functions | PledgeRiskAnalyzer.analyze() | Already built and tested in Phase 30 |
| JSON serialization for JSONB | Manual JSON string building | Pydantic model_dump() + SQLAlchemy JSONB column | Pydantic handles Decimal, date, None correctly |
| Narrative guardrails | Runtime number suppression in Python | Prompt-level instructions (NARR-02/03/04) | LLM generates narrative; guardrails belong in the prompt, not in post-processing |

**Key insight:** This phase is integration, not invention. All the complex logic (risk grading, combination rules, merge) exists in Phase 30's `pledge_risk_service.py`. This phase wires it into persistence + API + narrative.

## Runtime State Inventory

> This is a greenfield integration phase (new tables, column additions, API extension), not a rename/refactor. Runtime state inventory is not applicable.

## Common Pitfalls

### Pitfall 1: Pledge failure breaks financial risk API
**What goes wrong:** An unhandled exception in pledge data fetch/analysis propagates up to the API error handler, returning a 500 error even though financial risk (M-Score, F-Score) was computed successfully.
**Why it happens:** The pledge fetch/analysis code is not wrapped in a try/except, or the except catches only specific exception types.
**How to avoid:** Wrap the entire pledge block (fetch snapshot, fetch details, PledgeRiskAnalyzer.analyze, persist) in a single broad try/except. On any exception, construct a PledgeRiskResult with UNAVAILABLE freshness and return financial results normally.
**Warning signs:** API returns error when AKShare pledge endpoint is down but financial data is available.

### Pitfall 2: Frozen Pydantic model mutation
**What goes wrong:** Attempting to set pledge_risk or risk_level_breakdown on an existing frozen RiskScore instance raises ValidationError.
**Why it happens:** RiskScore has model_config = {"frozen": True}. The risk route creates risk_score from RiskAnalyzer.analyze() and then tries to add pledge fields.
**How to avoid:** Do NOT modify the RiskScore. Instead, build the response dict separately: merge pledge_risk_result data into the response model (RiskScoreWithNarrative) or use model_copy(update={...}) on a copy. The risk_level may need updating if pledge upgrades it -- this requires a new RiskScore or a response wrapper.
**Warning signs:** `ValidationError: Instance is frozen` at runtime when pledge risk is present.

### Pitfall 3: Alembic migration ordering conflict
**What goes wrong:** Migration 021 references revision "020" but the actual latest migration has a different revision ID format.
**Why it happens:** Migration 020 uses revision string "020" (verified in codebase). Previous migrations used hash-style IDs (e.g., "3330cc06df7c"). The chain must be consistent.
**How to avoid:** Verify down_revision = "020" matches the exact revision string in 020_market_scanner_tables.py. Already verified: revision = "020" in that file.
**Warning signs:** `alembic upgrade head` fails with revision not found.

### Pitfall 4: Replace-all details without transaction safety
**What goes wrong:** Delete + insert of pledge details is not atomic; if insert fails after delete, details are lost.
**Why it happens:** The replace_details_for_ticker deletes all rows then inserts new ones. If the session flush fails between delete and insert, data is gone.
**How to avoid:** The replace-all runs within the same session/transaction as the risk route's commit. If the overall transaction fails, the session rollback restores the deleted details. Ensure the route's existing transaction handling covers pledge persistence.
**Warning signs:** Pledge details disappear after a partial failure.

### Pitfall 5: Narrative implies low pledge risk when data unavailable
**What goes wrong:** LLM generates text like "质押风险较低" when pledge data is actually unavailable, misleading the user.
**Why it happens:** The prompt does not explicitly forbid this inference, or the LLM fills in the gap with a default assumption.
**How to avoid:** Prompt must contain an explicit instruction: "当质押数据不可得时，只能说明'质押数据不可得'，不得暗示质押风险较低或较高" (NARR-03). This is a critical guardrail.
**Warning signs:** Narrative text contains risk-level assertions about pledge data that was UNAVAILABLE.

### Pitfall 6: Missing pledge fields in RiskScoreCreate / upsert
**What goes wrong:** pledge_risk and risk_level_breakdown are added to RiskScoreDB ORM model but not to RiskScoreCreate Pydantic model or the upsert_by_report_id field_values dict, so they are never written to the database.
**Why it happens:** The create/upsert path has explicit field mapping (not using **kwargs), so new fields must be added to both the Pydantic model and the repository method.
**How to avoid:** Add pledge_risk and risk_level_breakdown to RiskScoreCreate, RiskScore (domain model), and the field_values dict in upsert_by_report_id. Test that these fields round-trip through create -> db -> read.
**Warning signs:** pledge_risk and risk_level_breakdown columns are always NULL in the database.

## Code Examples

### ORM Model: EquityPledgeSnapshotDB (verified pattern from RiskScoreDB + IndexConstituentDB)

```python
# Source: Verified from stockvaluefinder/db/models/risk.py + index_constituent.py patterns
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint

from stockvaluefinder.db.base import Base


class EquityPledgeSnapshotDB(Base):
    """SQLAlchemy ORM model for equity pledge snapshots."""

    __tablename__ = "equity_pledge_snapshots"

    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4,
        comment="Unique identifier",
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker"), nullable=False, index=True,
        comment="Stock code",
    )
    latest_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="Trade date of pledge data",
    )
    stock_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Stock name",
    )
    industry: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Industry classification",
    )
    company_pledge_ratio: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Company pledge ratio as percentage",
    )
    pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4), nullable=True, comment="Total pledged shares",
    )
    pledge_market_value: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4), nullable=True, comment="Market value of pledged shares",
    )
    pledge_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Number of pledge transactions",
    )
    unrestricted_pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4), nullable=True, comment="Unrestricted shares pledged",
    )
    restricted_pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4), nullable=True, comment="Restricted shares pledged",
    )
    one_year_price_change: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="One-year price change as percentage",
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Data source identifier",
    )
    source_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="Raw API response for audit traceability",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Data fetch timestamp",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )

    __table_args__ = (
        UniqueConstraint(
            "ticker", "latest_date", "source",
            name="uq_pledge_snapshot_ticker_date_src",
        ),
    )
```

### Risk route integration flow (verified pattern from risk_routes.py)

```python
# Source: Verified from stockvaluefinder/api/risk_routes.py lines 124-241
# PLUS tech design section 13.3 pseudocode

# After existing risk analysis (line 152):
risk_score = analyzer.analyze(current_report, previous_report)

# New pledge block (insert after line 152, before narrative generation):
pledge_risk_result: PledgeRiskResult | None = None
if request.include_pledge_risk:
    try:
        if not risk_score.ticker.endswith(".HK"):
            snapshot = await data_service.get_equity_pledge_snapshot(ticker)
            details = await data_service.get_equity_pledge_details(ticker)

            pledge_analyzer = PledgeRiskAnalyzer()
            pledge_risk_result = pledge_analyzer.analyze(
                ticker=ticker,
                snapshot=snapshot,
                details=details,
                financial_risk_level=risk_score.risk_level,
                financial_red_flags=risk_score.red_flags,
            )

            # Persist pledge data
            pledge_snapshot_repo = PledgeSnapshotRepository(db)
            pledge_detail_repo = PledgeDetailRepository(db)
            if snapshot is not None:
                await pledge_snapshot_repo.upsert_by_ticker_date_source(snapshot)
            if details:
                await pledge_detail_repo.replace_details_for_ticker(ticker, details)
        else:
            pledge_risk_result = PledgeRiskAnalyzer().analyze(
                ticker=ticker,
                snapshot=None,
                details=[],
                financial_risk_level=risk_score.risk_level,
                financial_red_flags=risk_score.red_flags,
            )
    except Exception:
        logger.warning(f"Pledge risk analysis failed for {ticker}", exc_info=True)
        pledge_risk_result = None
```

### Migration 021 structure (verified from 020 + 006 patterns)

```python
# Source: Verified from stockvaluefinder/alembic/versions/020_market_scanner_tables.py
# and stockvaluefinder/alembic/versions/006_add_narrative_columns.py

revision: str = "021"
down_revision: Union[str, Sequence[str], None] = "020"

def upgrade() -> None:
    # 1. Create equity_pledge_snapshots
    op.create_table("equity_pledge_snapshots", ...)
    op.create_index(...)

    # 2. Create equity_pledge_details
    op.create_table("equity_pledge_details", ...)
    op.create_index(...)

    # 3. Add nullable JSONB columns to risk_scores
    op.add_column("risk_scores", sa.Column("pledge_risk", JSONB, nullable=True, ...))
    op.add_column("risk_scores", sa.Column("risk_level_breakdown", JSONB, nullable=True, ...))

def downgrade() -> None:
    op.drop_column("risk_scores", "risk_level_breakdown")
    op.drop_column("risk_scores", "pledge_risk")
    op.drop_table("equity_pledge_details")
    op.drop_table("equity_pledge_snapshots")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate pledge risk endpoint | Embedded in risk API (D-02) | Phase 31 decision | Single API call, simpler client integration |
| Custom risk merge logic | Phase 30 PledgeRiskAnalyzer + merge_risk_levels | Phase 30 | Reusable, tested pure functions |
| Narrative without guardrails | Explicit prompt guardrails (NARR-02/03/04) | Phase 31 | Prevents LLM hallucination of pledge numbers |

**Deprecated/outdated:**
- None -- this is greenfield integration work.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ExternalDataService.get_equity_pledge_snapshot() and get_equity_pledge_details() are functional from Phase 29 | API Integration | Pledge data fetch would fail; route would fall back to graceful degradation |
| A2 | PledgeRiskAnalyzer.analyze() signature accepts (ticker, snapshot, details, financial_risk_level, financial_red_flags) as verified in pledge_risk_service.py | API Integration | Integration would need signature adaptation |
| A3 | The risk route's existing transaction handling (try/except with rollback at lines 196-198) covers the pledge persistence step | API Integration | Partial data persistence on failure |
| A4 | RiskScore model frozen=True prevents in-place mutation; response must use model_copy or a wrapper model | API Integration | ValidationError at runtime |
| A5 | Phase 30 RiskLevelBreakdown model already has all required fields (financial_risk_level, pledge_risk_level, final_risk_level, merge_reason) | Response Models | Response model would need additional fields |

**Note:** Assumptions A2 and A5 are directly verified from code reading in this session. A1 is based on Phase 29 existing and being marked complete. A3 and A4 are verified from reading risk_routes.py and models/risk.py respectively.

## Open Questions (RESOLVED)

1. **RiskScore response model approach**
   - What we know: RiskScore is frozen. RiskScoreWithNarrative extends RiskScore with narrative. Adding pledge_risk and risk_level_breakdown fields requires either extending RiskScore (breaking change for existing consumers) or creating a new response wrapper.
   - What's unclear: Whether to add optional pledge_risk/risk_level_breakdown fields directly to RiskScore model (with defaults None) or create a separate RiskScoreWithPledge response model.
   - Recommendation: Add optional fields (pledge_risk: dict | None = None, risk_level_breakdown: RiskLevelBreakdown | None = None) directly to RiskScore. Since they default to None, existing consumers see no change. This follows the D-02 decision to embed pledge data in the existing response.

2. **Narrative prompt: flat dict vs structured pledge_risk_result parameter**
   - What we know: build_risk_prompt() currently receives result_data: dict[str, Any] which is risk_score.model_dump(). The pledge data needs to be included for narrative generation.
   - What's unclear: Whether to add pledge data to the result_data dict before passing to build_risk_prompt, or add a separate pledge_data parameter.
   - Recommendation: Add a separate optional pledge_data parameter to build_risk_prompt(). This keeps the pledge section clearly delineated in the prompt template and makes conditional rendering easier.

## Environment Availability

> This phase has no new external dependencies. All required tools are already installed.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | YES | 3.14.4 | -- |
| uv | Package management | YES | 0.7.16 | -- |
| SQLAlchemy | ORM | YES | 2.0.47 | -- |
| Alembic | Migrations | YES | 1.18.4 | -- |
| Pydantic | Validation | YES | 2.12.5 | -- |
| FastAPI | API routes | YES | 0.133.1 | -- |
| PostgreSQL | Database | Assumed | -- | Migration tested via `alembic upgrade head` |
| pytest | Testing | YES | 9.0+ (via pyproject.toml) | -- |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | pytest.ini at project root |
| Quick run command | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -x` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | Snapshot table created with unique constraint | integration | `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py -x` | NO - Wave 0 |
| DB-02 | Detail table created with indexes | integration | `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py -x` | NO - Wave 0 |
| DB-03 | risk_scores extended with JSONB columns | integration | `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py -x` | NO - Wave 0 |
| DB-04 | source_raw JSONB preserved for audit | unit | `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py -x` | NO - Wave 0 |
| DB-05 | Upsert snapshot, replace-all details | unit | `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py -x` | NO - Wave 0 |
| DB-06 | Migration 021 runs without error | integration | `uv run alembic upgrade head` | N/A (manual) |
| API-01 | include_pledge_risk param works | unit | `uv run pytest tests/unit/test_api/test_risk_routes_pledge.py -x` | NO - Wave 0 |
| API-02 | Response includes pledge_risk object | unit | `uv run pytest tests/unit/test_api/test_risk_routes_pledge.py -x` | NO - Wave 0 |
| API-03 | Response includes risk_level_breakdown | unit | `uv run pytest tests/unit/test_api/test_risk_routes_pledge.py -x` | NO - Wave 0 |
| API-04 | Graceful degradation on pledge failure | unit | `uv run pytest tests/unit/test_api/test_risk_routes_pledge.py -x` | NO - Wave 0 |
| API-05 | HK returns supported=false | unit | `uv run pytest tests/unit/test_api/test_risk_routes_pledge.py -x` | NO - Wave 0 |
| NARR-01 | Narrative includes pledge paragraph | unit | `uv run pytest tests/unit/test_services/test_narrative_prompts_pledge.py -x` | NO - Wave 0 |
| NARR-02 | Prompt forbids fabricated numbers | unit | `uv run pytest tests/unit/test_services/test_narrative_prompts_pledge.py -x` | NO - Wave 0 |
| NARR-03 | Unavailable states "pledge data unavailable" | unit | `uv run pytest tests/unit/test_services/test_narrative_prompts_pledge.py -x` | NO - Wave 0 |
| NARR-04 | Null safety_margin omits closeout mention | unit | `uv run pytest tests/unit/test_services/test_narrative_prompts_pledge.py -x` | NO - Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_repositories/test_equity_pledge_repo.py tests/unit/test_api/test_risk_routes_pledge.py -x`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_repositories/test_equity_pledge_repo.py` -- covers DB-01 through DB-05
- [ ] `tests/unit/test_api/test_risk_routes_pledge.py` -- covers API-01 through API-05
- [ ] `tests/unit/test_services/test_narrative_prompts_pledge.py` -- covers NARR-01 through NARR-04

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing JWT auth via get_current_user dependency |
| V3 Session Management | yes | Existing token blacklist via Redis |
| V4 Access Control | yes | Existing require_stock_access dependency |
| V5 Input Validation | yes | Pydantic request validation (ticker pattern, include_pledge_risk bool) |
| V6 Cryptography | no | No new crypto operations |

### Known Threat Patterns for SQLAlchemy + FastAPI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via user input | Tampering | SQLAlchemy ORM parameterized queries (no raw SQL) |
| Mass assignment via request body | Tampering | Pydantic model with explicit field whitelist |
| Information disclosure in error messages | Information Disclosure | Generic error messages in API responses, detailed logging server-side only |
| Denial of service via pledge data fetch | Denial of Service | Existing rate_limit dependency; pledge fetch wrapped in try/except with timeout |

## Sources

### Primary (HIGH confidence)
- Codebase reading of `stockvaluefinder/db/models/risk.py` -- RiskScoreDB ORM pattern (JSONB columns, UUID PK, ForeignKey, indexes)
- Codebase reading of `stockvaluefinder/repositories/risk_repo.py` -- upsert_by_report_id pattern
- Codebase reading of `stockvaluefinder/api/risk_routes.py` -- risk analysis flow, transaction handling, dependency injection
- Codebase reading of `stockvaluefinder/services/narrative_prompts.py` -- build_risk_prompt pattern
- Codebase reading of `stockvaluefinder/services/narrative_service.py` -- graceful fallback pattern
- Codebase reading of `stockvaluefinder/models/equity_pledge.py` -- PledgeRiskResult, RiskLevelBreakdown models from Phase 30
- Codebase reading of `stockvaluefinder/services/pledge_risk_service.py` -- PledgeRiskAnalyzer.analyze() signature
- Codebase reading of `stockvaluefinder/alembic/versions/020_market_scanner_tables.py` -- table creation + index pattern
- Codebase reading of `stockvaluefinder/alembic/versions/006_add_narrative_columns.py` -- add-column pattern
- Codebase reading of `stockvaluefinder/alembic/versions/007_add_fscore_to_risk_scores.py` -- JSONB column addition pattern
- `doc/equity_pledge_risk_analysis_technical_design.md` -- Database schema (section 7), API integration (section 13), narrative (section 14)

### Secondary (MEDIUM confidence)
- CONTEXT.md canonical references cross-verified against actual codebase files

### Tertiary (LOW confidence)
- None -- all findings verified from codebase reading

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies verified in codebase, no new packages needed
- Architecture: HIGH - patterns verified from existing code, tech design doc confirms approach
- Pitfalls: HIGH - identified from reading actual code patterns and frozen model constraints

**Research date:** 2026-06-07
**Valid until:** 2026-07-07 (stable -- no fast-moving dependencies)
