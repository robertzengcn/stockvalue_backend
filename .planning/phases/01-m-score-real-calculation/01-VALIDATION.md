---
phase: 1
slug: m-score-real-calculation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-15
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 with hypothesis |
| **Config file** | `stockvaluefinder/pytest.ini` |
| **Quick run command** | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py -x -q` |
| **Full suite command** | `cd stockvaluefinder && uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py -x -q`
- **After every plan wave:** Run `cd stockvaluefinder && uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01 | 1 | RISK-01..10 | T-1-01 | MScoreData frozen, audit trail with source refs | unit | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreDataExtension -x -q` | ❌ W0 | ⬜ pending |
| 01-01-T2 | 01 | 1 | RISK-01..08 | T-1-01 | Field validation, nan rejection | unit | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreFieldMapping -x -q` | ❌ W0 | ⬜ pending |
| 01-02-T1 | 02 | 2 | RISK-01..08 | T-1-01 | Zero denom handling, strict mode | unit | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices -x -q` | ❌ W0 | ⬜ pending |
| 01-02-T2 | 02 | 2 | RISK-09, RISK-10 | T-1-01 | Audit trail in API response | unit | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_services/test_risk_service.py` — add `TestMScoreDataExtension` class with audit model tests
- [ ] `tests/unit/test_services/test_risk_service.py` — add `TestMScoreFieldMapping` class with data source mapping tests
- [ ] `tests/unit/test_services/test_risk_service.py` — add `TestMScoreIndices` class with all 8 index calculation tests
- [ ] `tests/unit/test_services/test_risk_service.py` — add Maotai manual verification test with known values

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| M-Score matches manual calculation for 600519.SH | RISK-03 | Requires live AKShare data | Run `uv run python -c "..."` with 600519.SH and compare with known values |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
