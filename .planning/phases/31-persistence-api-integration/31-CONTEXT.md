# Phase 31: Persistence & API Integration - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Pledge risk data is persisted in the database and integrated into the existing risk API endpoint with full narrative support and graceful degradation. This phase delivers: (1) ORM models + Alembic migration for pledge tables and risk_scores extension, (2) pledge data repository with upsert/replace-all, (3) risk API integration with include_pledge_risk parameter, (4) narrative prompt extension with guarded output rules.

**In scope:** DB-01 through DB-06 (persistence), API-01 through API-05 (API integration), NARR-01 through NARR-04 (narrative)
**Out of scope:** Data fetching (Phase 29), risk calculation (Phase 30), frontend UI
</domain>

<decisions>
## Implementation Decisions

### Persistence Scope
- **D-01:** Two separate new tables (equity_pledge_snapshots, equity_pledge_details) store raw pledge data from AKShare. Plus nullable JSONB columns (pledge_risk, risk_level_breakdown) on existing risk_scores table for computed PledgeRiskResult from Phase 30's PledgeRiskAnalyzer. Clean separation: raw data history vs analysis output.

### API Response Design
- **D-02:** Pledge risk is embedded in the existing POST /analyze/risk response. New request parameter include_pledge_risk=true (default). Response gains pledge_risk object and risk_level_breakdown fields. No separate endpoint. Single API call returns everything. Matches API-01/API-02/API-03.

### Migration Strategy
- **D-03:** Single Alembic migration 021 creates both new pledge tables AND adds nullable JSONB columns to risk_scores. Existing rows naturally get NULL values (standard nullable column behavior). Atomic and simple.

### Narrative Integration
- **D-04:** Extend existing build_risk_prompt() in narrative_prompts.py with a pledge risk paragraph section. Include guardrails: only use data from structured pledge_risk fields (NARR-02), no fabrication of pledge numbers, state "pledge data unavailable" when missing without implying low risk (NARR-03), omit closeout distance when safety_margin is null (NARR-04). Single LLM call.

### Claude's Discretion
- Exact ORM model field types and column definitions (follow existing RiskScoreDB pattern)
- Repository method signatures and upsert/replace-all logic (follow existing BaseRepository pattern)
- Response model structure for pledge_risk object in API response
- Alembic migration file naming and structure (follow existing migration pattern)
- Narrative prompt text and guardrail phrasing
- Error handling for pledge data fetch failures within the risk API flow

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### PRD & Technical Design
- `doc/equity_pledge_risk_analysis_prd.md` -- Product requirements, persistence requirements (§10), API requirements (§11), narrative requirements (§12)
- `doc/equity_pledge_risk_analysis_technical_design.md` -- Database schema design (§10), API integration (§11), narrative prompt design (§12), graceful degradation rules

### Requirements
- `.planning/REQUIREMENTS.md` -- DB-01 through DB-06, API-01 through API-05, NARR-01 through NARR-04 (locked requirements for this phase)

### Existing Code Patterns (MUST follow)
- `stockvaluefinder/db/models/risk.py` -- RiskScoreDB ORM model (column types, JSONB pattern, indexes)
- `stockvaluefinder/db/base.py` -- Base declarative model, get_db() async session
- `stockvaluefinder/repositories/base.py` -- Generic BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType]
- `stockvaluefinder/repositories/risk_repo.py` -- RiskScoreRepository with upsert_by_report_id pattern
- `stockvaluefinder/api/risk_routes.py` -- POST /analyze/risk endpoint (request/response models, transaction handling, graceful degradation)
- `stockvaluefinder/api/dependencies.py` -- get_initialized_data_service, get_db, auth dependencies
- `stockvaluefinder/models/risk.py` -- RiskScore domain model (frozen, field_serializer pattern)
- `stockvaluefinder/models/api.py` -- ApiResponse[T] generic envelope
- `stockvaluefinder/services/narrative_service.py` -- NarrativeService with graceful fallback pattern
- `stockvaluefinder/services/narrative_prompts.py` -- build_risk_prompt() template pattern

### Phase 30 Output (consumed by this phase)
- `stockvaluefinder/services/pledge_risk_service.py` -- PledgeRiskAnalyzer.analyze() produces PledgeRiskResult
- `stockvaluefinder/models/equity_pledge.py` -- EquityPledgeSnapshot, EquityPledgeDetail (input data), PledgeRiskResult, CompanyPledgeRisk, HolderPledgeRisk, CloseoutRisk, RiskLevelBreakdown (output models)
- `.planning/phases/30-pledge-risk-calculation/30-CONTEXT.md` -- Phase 30 decisions

### Phase 29 Output (data source)
- `stockvaluefinder/external/data_service.py` -- ExternalDataService.get_equity_pledge_snapshot(), get_equity_pledge_details()
- `.planning/phases/29-pledge-data-foundation/29-CONTEXT.md` -- Phase 29 decisions (bulk-cache-filter, zero-pledge handling)

### Database Migrations
- `stockvaluefinder/alembic/versions/` -- Existing migration files for numbering pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **RiskScoreDB** (db/models/risk.py): ORM pattern with UUID PK, ticker FK, JSONB columns (mscore_data, fscore_data), risk_level indexed. Phase 31 adds pledge_risk and risk_level_breakdown JSONB columns following same pattern.
- **BaseRepository** (repositories/base.py): Generic CRUD with TypeVar generics. PledgeSnapshotRepository and PledgeDetailRepository inherit from this.
- **RiskScoreRepository.upsert_by_report_id()** (repositories/risk_repo.py): Upsert pattern. Pledge repository uses upsert for snapshots, replace-all for details (per DB-05).
- **analyze_risk()** (api/risk_routes.py): Main risk endpoint with request validation, data fetch, analysis, persistence, narrative, response. Phase 31 adds pledge data fetch + PledgeRiskAnalyzer.analyze() + pledge persistence step within this same flow.
- **NarrativeService.generate_narrative()** (narrative_service.py): Graceful fallback to None on LLM failure. Pledge narrative follows same pattern.
- **build_risk_prompt()** (narrative_prompts.py): Structured JSON prompt builder. Phase 31 extends with pledge risk data section.

### Established Patterns
- **JSONB columns**: risk_scores already uses JSONB for mscore_data, fscore_data, red_flags. pledge_risk follows same pattern.
- **ApiResponse[T] envelope**: All API responses use generic envelope. Pledge data embedded in existing risk response, not wrapped separately.
- **Graceful degradation**: Risk API returns financial results even if LLM/pledge fails. Pledge failure sets data_quality.freshness=UNAVAILABLE with warning.
- **Frozen Pydantic models**: All result models frozen=True. Pledge risk result models already frozen from Phase 30.
- **Async repository**: All repos use AsyncSession. Pledge repos follow same async pattern.

### Integration Points
- **risk_routes.py analyze_risk()**: After existing RiskAnalyzer.analyze(), add pledge data fetch + PledgeRiskAnalyzer.analyze() + pledge persistence + pledge_risk JSONB on risk_scores
- **RiskAnalysisRequest**: Add include_pledge_risk: bool = True field
- **RiskScoreDB**: Add pledge_risk and risk_level_breakdown mapped_column(JSONB, nullable=True)
- **build_risk_prompt()**: Add pledge_risk_data parameter with structured fields for narrative generation
- **ExternalDataService**: Call get_equity_pledge_snapshot() and get_equity_pledge_details() within the risk analysis flow

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond what's in PRD and tech design docs. Follow established patterns consistently.
</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.
</deferred>

---

*Phase: 31-Persistence & API Integration*
*Context gathered: 2026-06-07*
