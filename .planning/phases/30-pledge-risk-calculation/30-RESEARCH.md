# Phase 30: Pledge Risk Calculation - Research

**Researched:** 2026-06-06
**Domain:** Equity pledge risk grading (pure calculation functions)
**Confidence:** HIGH

## Summary

Phase 30 implements the pure calculation layer for equity pledge risk grading. It consumes `EquityPledgeSnapshot` and `list[EquityPledgeDetail]` models (created in Phase 29) and produces structured risk results (`PledgeRiskResult`) that Phase 31 will persist and integrate into the risk API.

The domain is straightforward threshold-based risk grading across three dimensions (company ratio, holder ratio, closeout margin), plus five combination upgrade rules and a merge-into-financial-risk function. All thresholds are explicitly defined in the PRD and technical design documents. The implementation follows the exact same pattern as the existing `risk_service.py` which uses module-level pure functions and a thin `RiskAnalyzer` class.

**Primary recommendation:** Implement 8-10 pure functions in `pledge_risk_service.py` following the exact pattern of `risk_service.py` (module-level pure functions, no I/O, no async). Add result Pydantic models to the existing `equity_pledge.py` model file. The functions are deterministic, testable with no mocking needed, and can be validated against the explicit thresholds in the PRD tables.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Pledge risk calculation lives in a new `stockvaluefinder/services/pledge_risk_service.py` file with a `PledgeRiskAnalyzer` class, separate from the existing financial `RiskAnalyzer` in `risk_service.py`
- **D-02:** PledgeRiskAnalyzer exposes a single `analyze()` method that takes snapshot, details, and financial_risk_level, returning a `PledgeRiskResult` with all 3 grades, combination upgrades, red flags, and final merged level
- **D-03:** Result models (PledgeRiskResult, PledgeRiskGrade, CompanyPledgeRisk, HolderPledgeRisk, CloseoutRisk, RiskLevelBreakdown) are defined in `stockvaluefinder/models/equity_pledge.py` alongside existing pledge data models
- **D-04:** Each of the 5 combination upgrade rules (RISK-04) is a separate pure function (e.g., `check_high_pledge_with_price_drop`, `check_holder_over_80`, `check_closeout_margin_low`, `check_high_pledge_with_financial_high`, `check_high_pledge_with_存贷双高`)
- **D-05:** All 5 rules are always evaluated (no short-circuit) to produce a full audit trail. The highest upgrade wins. Each triggered rule adds a red flag.
- **D-06:** When multiple holders tie on pledged_to_holding_ratio, the first holder in the data source list order is selected. Document this tie-breaking behavior.
- **D-07:** Zero-pledge stocks (no shareholder details) return holder_risk_level=LOW with no controlling holder identified. Consistent with the zero-pledge snapshot pattern from Phase 29.
- **D-08:** Red flags are plain strings like '公司质押比例35.2%超过30%阈值' and '控股股东质押比例82%超过80%阈值', matching the existing `red_flags: list[str]` pattern in financial RiskScore

### Claude's Discretion
- Exact Pydantic model field types and validation rules (follow existing risk.py pattern)
- Private helper method names and signatures within PledgeRiskAnalyzer
- How PledgeRiskResult structures the combination_upgrade audit trail
- Error handling for None/missing numeric fields in pledge data (follow NaN-to-None pattern from Phase 29)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-01 | Company overall pledge risk level (LOW/MEDIUM/HIGH) based on company pledge ratio thresholds (<10% LOW, 10-20% LOW with note, 20-30% MEDIUM, >30% HIGH) | PRD section 6.1 defines exact thresholds. `determine_company_pledge_risk()` pure function. Input: `EquityPledgeSnapshot.company_pledge_ratio` (float, percentage). "Note" expressed via red_flags string, not a separate enum level (PRD section 9.1). |
| RISK-02 | Controlling shareholder pledge risk level based on holder pledge ratio thresholds (<30% LOW, 30-50% LOW with note, 50-80% MEDIUM, >80% HIGH) | PRD section 6.2. `determine_holder_pledge_risk()` pure function. Input: selected holder's `pledged_to_holding_ratio`. Same "note as red_flag" pattern as RISK-01. |
| RISK-03 | Closeout safety margin calculation: `(latest_price - estimated_closeout_price) / estimated_closeout_price * 100`. Risk level: >50% LOW, 30-50% LOW with note, 20-30% MEDIUM, <20% HIGH | Tech design section 9.3 formula. `calculate_closeout_safety_margin()` and `determine_closeout_risk()` pure functions. Returns None when inputs are None/invalid. HK tickers return supported=false. |
| RISK-04 | Five combination upgrade rules: (1) company_pledge>30% + 1yr_drop>-30% -> HIGH, (2) holder_pledge>80% -> HIGH, (3) closeout_margin<20% -> HIGH, (4) company_pledge>20% + financial HIGH -> final HIGH, (5) company_pledge>20% + 存贷双高 -> final HIGH | Tech design section 9.4. Each rule is a separate pure function (D-04). All always evaluated (D-05). Rules 4 and 5 cross the pledge-financial boundary (merge phase). |
| RISK-05 | Merge financial risk level and pledge risk level into final risk level; pledge can only upgrade, never downgrade | Tech design section 9.5. `merge_risk_levels()` pure function. Returns `(RiskLevel, RiskLevelBreakdown)` tuple. pledge_risk_level=None returns financial level unchanged. |
| RISK-06 | Structured red flags explaining each triggered risk condition with specific data values | Follows existing `red_flags: list[str]` pattern in RiskScore. Chinese format per D-08: e.g., '公司质押比例35.2%超过30%阈值'. Generated alongside each grading and upgrade rule. |
| RISK-07 | Data freshness: CURRENT (within 10 days), STALE (older), UNAVAILABLE (no data) based on trade date of pledge snapshot | `DataFreshness` enum already exists in `enums.py` (defined in Phase 29). Computed from `EquityPledgeSnapshot.latest_date` vs today's date. `determine_data_freshness()` pure function using `datetime.date` comparison. |
| RISK-08 | Identify controlling shareholder: holder with highest pledged_to_holding_ratio among top holders | Tech design section 9.2. `find_controlling_holder()` pure function. Input: `list[EquityPledgeDetail]`. Tie-breaking: first in list order (D-06). Zero-pledge: returns None, risk_level=LOW (D-07). |
| RISK-09 | HK tickers return supported=false with appropriate warning | Market detection from ticker suffix (.HK). `PledgeRiskResult.supported=False`. `data_quality.freshness=UNAVAILABLE`. Warning string in `data_quality.warnings`. No pledge calculations attempted. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Company pledge risk grading | Service layer (pure functions) | -- | Pure calculation, no I/O, identical to existing RiskAnalyzer pattern |
| Holder identification | Service layer (pure functions) | -- | Pure data transformation: find max ratio in a list |
| Closeout margin calculation | Service layer (pure functions) | -- | Arithmetic formula, no external dependencies |
| Combination upgrade rules | Service layer (pure functions) | -- | Boolean logic on already-computed values |
| Risk level merging | Service layer (pure functions) | -- | Comparison of two RiskLevel enums |
| Red flag generation | Service layer (pure functions) | -- | String formatting with threshold data |
| Data freshness classification | Service layer (pure functions) | -- | Date arithmetic against current date |
| HK market detection | Service layer (pure functions) | -- | String suffix check on ticker format |

All capabilities in this phase are pure service-layer functions. No database, no API, no external calls. This phase has zero I/O -- every function is deterministic and testable without mocks.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Language runtime | Project constraint (pyproject.toml) |
| Pydantic | 2.12+ | Data models, validation | Already used for all domain models (RiskScore, EquityPledgeSnapshot, etc.) |
| pytest | 9.0+ | Testing | Project standard (pytest.ini, asyncio_mode=auto) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.3+ | Async test support | Not needed for this phase -- all functions are synchronous pure functions |
| hypothesis | 6.15+ | Property-based testing | Threshold boundary testing: random ratio values near 10%, 20%, 30%, 50%, 80% boundaries |
| pytest-cov | 7.0+ | Coverage reporting | Configured in pytest.ini addopts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hypothesis for boundary tests | Manual parametrize | hypothesis excels at finding boundary bugs in threshold functions -- worth using here |

**Installation:** No new packages needed. All dependencies already in pyproject.toml.

## Package Legitimacy Audit

No new packages are installed in this phase. All code is pure Python using existing dependencies.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
EquityPledgeSnapshot (Phase 29)  --+
                                   |
list[EquityPledgeDetail] (Phase 29)-+
                                   |
                                   v
                          +---------------------+
                          | PledgeRiskAnalyzer   |
                          |   .analyze()        |
                          +----------+----------+
                                   |
                    +--------------+--------------+
                    v              v               v
           +---------------+ +-------------+ +----------------+
           | Grade Company  | | Grade Holder | | Grade Closeout |
           | Ratio Risk     | | Pledge Risk  | | Margin Risk    |
           | (RISK-01)      | | (RISK-02,08) | | (RISK-03)      |
           +------+--------+ +------+------++ +------+---------+
                  |                |      |         |
                  +----------------+------+---------+
                                   |
                    +--------------+--------------+
                    | 5 Combination Upgrade Rules |
                    | (RISK-04)                   |
                    | All evaluated, no shortcut  |
                    +----------+---------+--------+
                               |         |
              +----------------+         |
              v                          v
   +-------------------------+   +------------------+
   | Red Flag Generation     |   | Risk Level Merge  |
   | (RISK-06)               |   | (RISK-05)         |
   +----------+--------------+   | pledge >= financial|
              |                   +--------+---------+
              |                            |
              +------------+---------------+
                           |
                           v
                   PledgeRiskResult
                   (consumed by Phase 31)
```

### Recommended Project Structure
```
stockvaluefinder/
  models/
    equity_pledge.py        # ADD result models (PledgeRiskResult, etc.) to existing file
  services/
    pledge_risk_service.py  # NEW: pure calculation functions + PledgeRiskAnalyzer
tests/
  unit/
    test_services/
      test_pledge_risk_service.py  # NEW: comprehensive threshold tests
```

### Pattern 1: Threshold Grading Pure Function
**What:** Map a continuous numeric value to a discrete risk level using explicit threshold boundaries.
**When to use:** Every risk dimension (company ratio, holder ratio, closeout margin) follows this pattern.
**Example:**
```python
def determine_company_pledge_risk(
    company_pledge_ratio: float | None,
) -> tuple[RiskLevel, list[str]]:
    """Grade company overall pledge ratio into risk level.

    Thresholds from PRD section 6.1:
        < 10%  -> LOW
        10-20% -> LOW  + note red flag
        20-30% -> MEDIUM
        > 30%  -> HIGH

    Returns:
        (RiskLevel, list of note strings for borderline/additional context)
    """
    if company_pledge_ratio is None:
        return RiskLevel.LOW, ["质押比例数据不可得"]

    notes: list[str] = []
    if company_pledge_ratio < 10:
        level = RiskLevel.LOW
    elif company_pledge_ratio < 20:
        level = RiskLevel.LOW
        notes.append(
            f"公司质押比例{company_pledge_ratio:.1f}%处于10%-20%关注区间"
        )
    elif company_pledge_ratio <= 30:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.HIGH

    return level, notes
```

### Pattern 2: Combination Upgrade Rule
**What:** Boolean check on a combination of conditions that triggers a risk level upgrade.
**When to use:** All 5 rules in RISK-04.
**Example:**
```python
def check_high_pledge_with_price_drop(
    company_pledge_ratio: float | None,
    one_year_price_change: float | None,
) -> tuple[bool, str | None]:
    """Check: company_pledge > 30% AND 1yr drop > 30% -> at least HIGH.

    Returns:
        (triggered, red_flag_or_none)
    """
    if company_pledge_ratio is None or one_year_price_change is None:
        return False, None
    if company_pledge_ratio > 30 and one_year_price_change < -30:
        return True, (
            f"公司质押比例{company_pledge_ratio:.1f}%超30%且"
            f"近一年跌幅{one_year_price_change:.1f}%超30%"
        )
    return False, None
```

### Pattern 3: Risk Level Merge (Upgrade Only)
**What:** Take the higher of two risk levels, preserving financial risk as baseline.
**When to use:** Final step to produce the merged risk level (RISK-05).
**Example:**
```python
_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

def merge_risk_levels(
    financial_risk_level: RiskLevel,
    pledge_risk_level: RiskLevel | None,
) -> tuple[RiskLevel, RiskLevelBreakdown]:
    """Merge financial and pledge risk. Pledge can only upgrade."""
    if pledge_risk_level is None:
        return financial_risk_level, RiskLevelBreakdown(
            financial_risk_level=financial_risk_level,
            pledge_risk_level=None,
            final_risk_level=financial_risk_level,
            merge_reason=None,
        )

    final = max(
        financial_risk_level,
        pledge_risk_level,
        key=lambda r: _RISK_ORDER[r],
    )
    reason = None
    if _RISK_ORDER[pledge_risk_level] > _RISK_ORDER[financial_risk_level]:
        reason = (
            f"质押风险{pledge_risk_level.value}"
            f"升级了财务风险{financial_risk_level.value}"
        )

    return final, RiskLevelBreakdown(
        financial_risk_level=financial_risk_level,
        pledge_risk_level=pledge_risk_level,
        final_risk_level=final,
        merge_reason=reason,
    )
```

### Anti-Patterns to Avoid
- **Mutating input models:** EquityPledgeSnapshot and EquityPledgeDetail are frozen=True. Never try to modify them.
- **Async in pure functions:** All grading functions must be synchronous. The `PledgeRiskAnalyzer.analyze()` method itself is synchronous -- it only receives already-fetched data.
- **Accessing external services:** This phase does NOT call ExternalDataService, Redis, or any I/O. Data comes in as function arguments.
- **Creating new enum levels:** RiskLevel has LOW/MEDIUM/HIGH/CRITICAL. The PRD "watch/note" level is expressed as a LOW with a red_flag string, NOT a new enum value.
- **Treating None as zero:** None means "data unavailable" and should result in LOW risk level (no data = no evidence of risk), NOT zero. Zero pledge ratio is an actual data value (confirmed zero pledges).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Risk level ordering comparison | Custom string/int comparison | `_RISK_ORDER` dict mapping to int | RiskLevel is a StrEnum, not naturally orderable. Explicit ordering dict is clear and maintainable. |
| Data freshness calculation | Custom business-day calendar | Simple `(date.today() - snapshot_date).days <= 10` | PRD section 11.3 says "先用自然日阈值" (use calendar days first). Trading calendar is V2. |
| Closeout margin formula | Complex safety margin class | Single-line formula: `(price - closeout) / closeout * 100` | Formula is explicitly defined in tech design section 9.3. No edge case handling beyond None/zero checks. |

**Key insight:** This phase is almost entirely threshold lookups and boolean combinations. The "trickiest" part is the combination upgrade rule logic, but even that is straightforward given the explicit PRD tables. No numerical precision issues, no floating point edge cases beyond what standard Python float handles.

## Common Pitfalls

### Pitfall 1: Confusing "note" with a risk level
**What goes wrong:** Implementing 10-20% company ratio or 30-50% holder ratio as a separate MEDIUM or WATCH risk level.
**Why it happens:** The PRD tables list "关注" (watch/attention) as an intermediate grade, which looks like a 4th level.
**How to avoid:** The tech design (section 9.1) explicitly states: "现有 RiskLevel 没有 WATCH，因此'关注'在后端不新增枚举，作为 red_flags 或 narrative 表达". These ranges return LOW with an additional note string appended to red_flags.
**Warning signs:** Code that tries to create a WATCH enum or returns MEDIUM for 10-20% company ratio.

### Pitfall 2: Not handling None inputs for numeric fields
**What goes wrong:** Crashing on `company_pledge_ratio > 30` when the value is None (data unavailable).
**Why it happens:** Phase 29 returns None for many fields when data is unavailable. Not all snapshot fields are guaranteed present.
**How to avoid:** Every grading function must accept `float | None` and handle None explicitly. None input -> LOW risk level (no data = no evidence of risk). This matches the PRD principle: "当数据缺失或来源不可用时，系统应返回数据不可得状态" -- but for individual risk dimensions, None means "cannot assess" which maps to LOW for that dimension. The UNAVAILABLE data freshness flag handles the overall "data missing" signal.
**Warning signs:** Type hints showing only `float` instead of `float | None`.

### Pitfall 3: Combination rules 4 and 5 cross the pledge-financial boundary
**What goes wrong:** Rules 4 and 5 (company_pledge > 20% + financial HIGH/存贷双高) need financial risk data that the pledge analyzer doesn't naturally own.
**Why it happens:** The `PledgeRiskAnalyzer.analyze()` method receives `financial_risk_level` and financial red flags as input (per D-02), but the combination rules need to check specific financial conditions (存贷双高 flag), not just the level.
**How to avoid:** Pass `financial_red_flags: list[str]` into analyze() alongside `financial_risk_level`. Check for "存贷双高" substring in financial red flags for rule 5. The `RiskAnalyzer` already generates this exact string: "存贷双高: High cash and high debt anomaly detected".
**Warning signs:** Rule 5 implementation that receives a boolean flag instead of checking financial red flags.

### Pitfall 4: Forgetting that company_pledge_ratio is stored as percentage
**What goes wrong:** Comparing against 0.30 instead of 30.0 because of confusion about whether the ratio is decimal (0-1) or percentage (0-100).
**Why it happens:** AKShare returns percentage values, and Phase 29 explicitly stores them as percentages (confirmed in STATE.md decision: "company_pledge_ratio stored as percentage matching AKShare raw format").
**How to avoid:** All threshold comparisons use integer values (10, 20, 30, 50, 80) not decimal fractions (0.1, 0.2, 0.3).
**Warning signs:** Code that multiplies or divides by 100 before threshold comparison.

### Pitfall 5: Zero-pledge stocks vs data-unavailable stocks
**What goes wrong:** Treating a stock with zero pledges (company_pledge_ratio=0.0, no details) the same as a stock with unavailable data (snapshot is None).
**Why it happens:** Both cases have "no pledge details", but they are semantically different. Zero-pledge is a valid data result; unavailable means the data source failed.
**How to avoid:** D-07 says zero-pledge returns holder_risk_level=LOW. When snapshot.data_quality.freshness is UNAVAILABLE, the whole result should reflect that. The analyze() method checks freshness first and short-circuits to UNAVAILABLE result.
**Warning signs:** Code that returns LOW risk for both cases without checking freshness.

## Code Examples

### Closeout Safety Margin Calculation
```python
def calculate_closeout_safety_margin(
    latest_price: float | None,
    estimated_closeout_price: float | None,
) -> float | None:
    """Calculate closeout safety margin as percentage above closeout price.

    Formula (tech design section 9.3):
        margin = (latest_price - estimated_closeout_price)
                 / estimated_closeout_price * 100

    Returns None if either input is None or closeout_price <= 0.
    """
    if latest_price is None or estimated_closeout_price is None:
        return None
    if estimated_closeout_price <= 0:
        return None
    return (latest_price - estimated_closeout_price) / estimated_closeout_price * 100
```

### Controlling Holder Identification
```python
def find_controlling_holder(
    details: list[EquityPledgeDetail],
) -> EquityPledgeDetail | None:
    """Identify controlling shareholder: highest pledged_to_holding_ratio.

    Per D-06: ties broken by first-in-list order.
    Per D-07: empty details returns None (zero-pledge stocks).
    """
    if not details:
        return None

    best: EquityPledgeDetail | None = None
    best_ratio = -1.0
    for detail in details:
        ratio = detail.pledged_to_holding_ratio
        if ratio is not None and ratio > best_ratio:
            best_ratio = ratio
            best = detail
    return best
```

### Data Freshness Classification
```python
from datetime import date

def determine_data_freshness(
    latest_date: date | None,
    reference_date: date | None = None,
) -> DataFreshness:
    """Classify data freshness based on days since snapshot date.

    Per PRD section 11.3:
        CURRENT: within 10 calendar days
        STALE: older than 10 calendar days
        UNAVAILABLE: no data (latest_date is None)
    """
    if latest_date is None:
        return DataFreshness.UNAVAILABLE

    ref = reference_date or date.today()
    days_diff = (ref - latest_date).days
    if days_diff <= 10:
        return DataFreshness.CURRENT
    return DataFreshness.STALE
```

### HK Ticker Detection
```python
def is_hk_ticker(ticker: str) -> bool:
    """Check if ticker is a Hong Kong stock code."""
    return ticker.endswith(".HK")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A -- new feature | Threshold-based risk grading | N/A | Pattern already established by risk_service.py's determine_risk_level() |

**Deprecated/outdated:**
- None for this phase. This is a new feature with no legacy patterns to replace.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `one_year_price_change` is stored as negative percentage for drops (e.g., -35.0 for 35% drop) | RISK-04 combination rule | Rule 1 threshold check direction is inverted |
| A2 | Financial red flag string for 存贷双高 contains substring "存贷双高" | Pitfall 3, RISK-04 rule 5 | Rule 5 detection fails -- would need different matching strategy |
| A3 | RiskLevel.CRITICAL will never be output by pledge risk grading (only LOW/MEDIUM/HIGH used) | Risk merge | If CRITICAL is possible, merge logic needs to handle 4-level ordering |

**Mitigation for assumptions:**
- A1: Verified from Phase 29 -- `one_year_price_change` maps directly from AKShare "近一年涨跌幅" which returns negative values for drops. Verified in data_service.py mapping.
- A2: Verified from risk_service.py line 750: the exact string is "存贷双高: High cash and high debt anomaly detected". Substring match on "存贷双高" will work.
- A3: The thresholds only produce LOW/MEDIUM/HIGH. CRITICAL exists in the enum but is only produced by the financial RiskAnalyzer when M-Score is bad AND red_flags >= 3. The merge function should still handle CRITICAL correctly for the financial_risk_level input.

## Open Questions (RESOLVED)

1. **Should `analyze()` be a class method or standalone function?**
   - What we know: D-01 says `PledgeRiskAnalyzer` class with `analyze()` method. D-02 says it takes snapshot + details + financial_risk_level.
   - What's unclear: Whether the class holds any state or is just a namespace like RiskAnalyzer (which has an empty `__init__`).
   - Recommendation: Follow RiskAnalyzer pattern exactly -- stateless class, thin wrapper over module-level pure functions.

2. **Should PledgeRiskResult include the individual dimension grades separately or just the final level?**
   - What we know: D-02 says "returning a PledgeRiskResult with all 3 grades, combination upgrades, red flags, and final merged level". Tech design section 8 shows `EquityPledgeRisk` with flat fields.
   - What's unclear: Whether there should be nested sub-models (CompanyPledgeRisk, HolderPledgeRisk, CloseoutRisk) as D-03 mentions, or flat fields on PledgeRiskResult.
   - Recommendation: Use nested sub-models for each dimension -- this gives the planner maximum flexibility for the API response structure in Phase 31.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies -- this phase is pure calculation functions with no I/O)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode=auto, cov enabled) |
| Quick run command | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -x` |
| Full suite command | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-01 | Company pledge ratio grading at all threshold boundaries (9%, 10%, 15%, 20%, 25%, 30%, 35%, None) | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_determine_company_pledge_risk -x` | Wave 0 |
| RISK-02 | Holder pledge ratio grading at all thresholds (25%, 30%, 40%, 50%, 65%, 80%, 85%, None) | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_determine_holder_pledge_risk -x` | Wave 0 |
| RISK-03 | Closeout margin calculation and grading (formula correctness, boundary values, None inputs, zero closeout) | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_closeout_margin -x` | Wave 0 |
| RISK-04 | Each of 5 combination rules: triggered and not-triggered cases with specific threshold values | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_combination_rules -x` | Wave 0 |
| RISK-05 | Risk merge: pledge upgrades, no upgrade, pledge=None, CRITICAL handling | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_merge_risk_levels -x` | Wave 0 |
| RISK-06 | Red flag string format and content verification | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_red_flags -x` | Wave 0 |
| RISK-07 | Data freshness: CURRENT (<10 days), STALE (>10 days), UNAVAILABLE (None) | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_data_freshness -x` | Wave 0 |
| RISK-08 | Holder identification: single best, tie-breaking (first in list), empty list, None ratios | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_find_controlling_holder -x` | Wave 0 |
| RISK-09 | HK ticker detection and unsupported result structure | unit | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py::test_hk_unsupported -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -x`
- **Per wave merge:** `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_services/test_pledge_risk_service.py` -- covers RISK-01 through RISK-09

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in this phase -- pure functions |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No access control in pure functions |
| V5 Input Validation | yes | Pydantic models validate input types; None handling for all optional fields |
| V6 Cryptography | no | No crypto |

### Known Threat Patterns for Pure Calculation Layer

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Invalid threshold values (e.g., negative ratio) | Tampering | Pydantic field validation + boundary checks in grading functions |
| NaN/inf propagation | Denial of Service | Explicit None/NaN checks before arithmetic (follow risk_service.py pattern) |

## Sources

### Primary (HIGH confidence)
- `doc/equity_pledge_risk_analysis_prd.md` - PRD sections 6.1-6.4 (threshold tables), section 8.2 (risk calculation requirements), section 11 (acceptance criteria)
- `doc/equity_pledge_risk_analysis_technical_design.md` - Sections 9.1-9.5 (risk grading formulas, combination rules, merge logic), section 11.3 (data freshness), section 8 (Pydantic model specs)
- `stockvaluefinder/services/risk_service.py` - Existing RiskAnalyzer pattern (module-level pure functions, determine_risk_level, red flag generation) [VERIFIED: codebase read]
- `stockvaluefinder/models/risk.py` - RiskScore model pattern (frozen=True, field descriptions) [VERIFIED: codebase read]
- `stockvaluefinder/models/equity_pledge.py` - Input models (EquityPledgeSnapshot, EquityPledgeDetail, EquityPledgeDataQuality) [VERIFIED: codebase read]
- `stockvaluefinder/models/enums.py` - RiskLevel and DataFreshness enums [VERIFIED: codebase read]

### Secondary (MEDIUM confidence)
- `.planning/phases/29-pledge-data-foundation/29-CONTEXT.md` - Phase 29 decisions on zero-pledge handling, NaN normalization, field maps
- `.planning/STATE.md` - Accumulated project decisions [VERIFIED: codebase read]

### Tertiary (LOW confidence)
- None -- all claims verified from codebase or PRD/tech design docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, pure Python using existing project patterns
- Architecture: HIGH - Follows exact same pattern as risk_service.py (826 lines, already proven)
- Pitfalls: HIGH - Identified from PRD/tech design explicit statements and existing code review
- Thresholds: HIGH - All 9 requirement thresholds explicitly defined in PRD tables, verified in tech design

**Research date:** 2026-06-06
**Valid until:** 30 days (stable domain -- financial risk thresholds are defined by PRD, not by library versions)
