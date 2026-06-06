# Phase 30: Pledge Risk Calculation - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

System grades equity pledge risk across company ratio, controlling shareholder ratio, and closeout safety margin, applying combination upgrade rules and merging with financial risk. This phase delivers pure calculation functions (PledgeRiskAnalyzer) that consume data from Phase 29 (EquityPledgeSnapshot, EquityPledgeDetail) and produce structured risk results for Phase 31 (persistence and API integration).

**In scope:** RISK-01 through RISK-09 (risk grading, combination rules, merge logic, red flag generation, data freshness, holder identification, HK unsupported)
**Out of scope:** Data fetching (Phase 29), DB persistence/API integration (Phase 31), narrative generation (Phase 31)
</domain>

<decisions>
## Implementation Decisions

### Service Architecture
- **D-01:** Pledge risk calculation lives in a new `stockvaluefinder/services/pledge_risk_service.py` file with a `PledgeRiskAnalyzer` class, separate from the existing financial `RiskAnalyzer` in `risk_service.py`
- **D-02:** PledgeRiskAnalyzer exposes a single `analyze()` method that takes snapshot, details, and financial_risk_level, returning a `PledgeRiskResult` with all 3 grades, combination upgrades, red flags, and final merged level
- **D-03:** Result models (PledgeRiskResult, PledgeRiskGrade, CompanyPledgeRisk, HolderPledgeRisk, CloseoutRisk, RiskLevelBreakdown) are defined in `stockvaluefinder/models/equity_pledge.py` alongside existing pledge data models

### Combination Rules Structure
- **D-04:** Each of the 5 combination upgrade rules (RISK-04) is a separate pure function (e.g., `check_high_pledge_with_price_drop`, `check_holder_over_80`, `check_closeout_margin_low`, `check_high_pledge_with_financial_high`, `check_high_pledge_with_存贷双高`)
- **D-05:** All 5 rules are always evaluated (no short-circuit) to produce a full audit trail. The highest upgrade wins. Each triggered rule adds a red flag.

### Controlling Shareholder Edge Cases
- **D-06:** When multiple holders tie on pledged_to_holding_ratio, the first holder in the data source list order is selected. Document this tie-breaking behavior.
- **D-07:** Zero-pledge stocks (no shareholder details) return holder_risk_level=LOW with no controlling holder identified. Consistent with the zero-pledge snapshot pattern from Phase 29.

### Red Flag Format
- **D-08:** Red flags are plain strings like '公司质押比例35.2%超过30%阈值' and '控股股东质押比例82%超过80%阈值', matching the existing `red_flags: list[str]` pattern in financial RiskScore

### Claude's Discretion
- Exact Pydantic model field types and validation rules (follow existing risk.py pattern)
- Private helper method names and signatures within PledgeRiskAnalyzer
- How PledgeRiskResult structures the combination_upgrade audit trail
- Error handling for None/missing numeric fields in pledge data (follow NaN-to-None pattern from Phase 29)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### PRD & Technical Design
- `doc/equity_pledge_risk_analysis_prd.md` -- Product requirements, risk grading thresholds, combination rules, acceptance criteria
- `doc/equity_pledge_risk_analysis_technical_design.md` -- Architecture, risk grading formulas (§7), combination rules (§7.4), merge logic (§7.5), data quality rules (§11.3)

### Requirements
- `.planning/REQUIREMENTS.md` -- RISK-01 through RISK-09 (locked requirements for this phase)

### Existing Code Patterns
- `stockvaluefinder/services/risk_service.py` -- Existing RiskAnalyzer class with analyze() method, determine_risk_level(), red flag generation pattern
- `stockvaluefinder/models/risk.py` -- RiskScore, MScoreData, FScoreData models (pattern to follow)
- `stockvaluefinder/models/equity_pledge.py` -- EquityPledgeSnapshot, EquityPledgeDetail, DataFreshness (data consumed by this phase)

### Prior Phase Context
- `.planning/phases/29-pledge-data-foundation/29-CONTEXT.md` -- Phase 29 decisions (bulk-cache-filter, zero-pledge handling, data quality)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **RiskAnalyzer** (`risk_service.py`): Pattern for analyze() method returning a structured result with risk_level, red_flags, audit_trail. PledgeRiskAnalyzer follows same pattern
- **determine_risk_level()** (`risk_service.py`): Threshold-to-level mapping pattern. Reuse for pledge risk thresholds
- **RiskLevel enum** (`enums.py`): LOW, MEDIUM, HIGH, CRITICAL. Pledge risk uses same levels
- **DataFreshness enum** (`enums.py`): CURRENT, STALE, UNAVAILABLE. Already defined in Phase 29, consumed here for RISK-07
- **EquityPledgeSnapshot/Detail** (`equity_pledge.py`): Input data models from Phase 29. PledgeRiskAnalyzer consumes these directly

### Established Patterns
- **Frozen Pydantic models**: All result models should be frozen=True following RiskScore pattern
- **Pure calculation functions**: risk_service.py uses module-level pure functions. Pledge risk should follow same pattern
- **Red flags as list[str]**: Existing financial risk uses plain strings. Pledge risk follows same format for consistency
- **Error wrapping**: External data errors wrapped in ExternalAPIError. Calculation errors wrapped in CalculationError

### Integration Points
- **PledgeRiskAnalyzer** consumes `EquityPledgeSnapshot` and `list[EquityPledgeDetail]` from Phase 29's ExternalDataService
- **Merge logic** takes `RiskLevel` (financial) and `RiskLevel` (pledge) and returns merged `RiskLevel`
- **Phase 31** will consume `PledgeRiskResult` to persist in DB and integrate into risk API response
</code_context>

<specifics>
## Specific Ideas

No specific requirements -- implementation follows established patterns from existing risk service and the detailed PRD/tech design documents.
</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.
</deferred>

---

*Phase: 30-Pledge Risk Calculation*
*Context gathered: 2026-06-06*
