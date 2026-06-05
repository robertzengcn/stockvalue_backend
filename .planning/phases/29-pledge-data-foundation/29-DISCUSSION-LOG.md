# Phase 29: Pledge Data Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 29-Pledge Data Foundation
**Areas discussed:** Ticker Normalization Edge Cases, Bulk vs Per-Stock API Design, Missing Ticker Handling

---

## Ticker Normalization Edge Cases

| Option | Description | Selected |
|--------|-------------|----------|
| SH/SZ only, reject BSE | 6xx->SH, 0xx/3xx->SZ, 8xx/4xx excluded. Log warning. | ✓ |
| Include BSE (.BJ suffix) | 6xx->SH, 0xx/3xx->SZ, 8xx/4xx->BJ. | |
| You decide | Follow codebase patterns. | |

**User's choice:** SH/SZ only, reject BSE
**Notes:** CSI 300/500 doesn't include BSE stocks.

### Normalizer location

| Option | Description | Selected |
|--------|-------------|----------|
| validators.py utility | Reusable by any module. | ✓ |
| AKShareClient private method | Close to data source. | |
| New stock_utils.py | Dedicated module. | |

**User's choice:** validators.py utility

### Error handling for unsupported prefixes

| Option | Description | Selected |
|--------|-------------|----------|
| Return None + warn | Pure function, caller handles. | ✓ |
| Raise DataValidationError | Forces explicit handling. | |

**User's choice:** Return None + warn

### Validation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Format-only | 6 digits, numeric. | |
| Format + prefix | Validate format AND prefix (0xx/3xx/6xx). | ✓ |

**User's choice:** Format + prefix validation

---

## Bulk vs Per-Stock API Design

### Interface granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-ticker with hidden bulk | Fetch bulk, cache, filter. Simple interface. | ✓ |
| Dual interface | Both bulk and per-ticker exposed. | |
| You decide | Follow existing patterns. | |

**User's choice:** Per-ticker with hidden bulk

### Caching strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Cache bulk, filter on read | One entry per date, amortized. | ✓ |
| Per-ticker cache entries | 5000 entries per date. Wasteful. | |

**User's choice:** Cache bulk, filter on read

### Detail API pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Same as ratio data | Consistent pattern. | ✓ |
| Per-ticker for details | Different pattern. | |

**User's choice:** Same as ratio data

---

## Missing Ticker Handling

### Absent ticker interpretation

| Option | Description | Selected |
|--------|-------------|----------|
| Zero pledge = valid empty | Return snapshot with ratio=0. | ✓ |
| Return None (unavailable) | Conservative, may over-flag. | |

**User's choice:** Zero pledge = valid empty result

### Distinguishing zero from failure

| Option | Description | Selected |
|--------|-------------|----------|
| Infer from bulk health | Non-empty bulk + missing = zero. Empty = UNAVAILABLE. | ✓ |
| Always zero pledges | Simpler, can't detect failures. | |

**User's choice:** Infer from bulk response health

### Zero-pledge response shape

| Option | Description | Selected |
|--------|-------------|----------|
| Full snapshot with ratio=0 | Consistent interface. | ✓ |
| Minimal response with note | Less data. | |

**User's choice:** Full snapshot with ratio=0

---

## Claude's Discretion

No areas deferred to Claude — user made all decisions directly.

## Deferred Ideas

None — discussion stayed within phase scope.
