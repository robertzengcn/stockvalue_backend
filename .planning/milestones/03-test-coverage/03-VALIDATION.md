---
phase: 03
slug: test-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | stockvaluefinder/pytest.ini |
| **Quick run command** | `uv run pytest tests/unit/test_services/ -x -q` |
| **Full suite command** | `uv run pytest --cov=stockvaluefinder --cov-report=term-missing -v` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_services/ -x -q`
- **After every plan wave:** Run `uv run pytest --cov=stockvaluefinder -v`
- **Before `/gsd-verify-work`:** Full suite must be green with 80%+ coverage
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | TEST-01 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) | ⬜ pending |
| 03-01-02 | 01 | 1 | TEST-01 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) | ⬜ pending |
| 03-01-03 | 01 | 1 | TEST-01 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) | ⬜ pending |
| 03-01-04 | 01 | 1 | TEST-01 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | N (add) | ⬜ pending |
| 03-02-01 | 02 | 1 | TEST-02 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | Y (extend) | ⬜ pending |
| 03-02-02 | 02 | 1 | TEST-02 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | N (add) | ⬜ pending |
| 03-02-03 | 02 | 1 | TEST-02 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | N (add) | ⬜ pending |
| 03-03-01 | 03 | 1 | TEST-03 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | Y (extend) | ⬜ pending |
| 03-03-02 | 03 | 1 | TEST-03 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | N (add) | ⬜ pending |
| 03-03-03 | 03 | 1 | TEST-03 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | N (add) | ⬜ pending |
| 03-04-01 | 04 | 2 | TEST-04 | — | N/A | unit | `uv run pytest tests/unit/test_external/test_data_service.py -x` | Y (extend) | ⬜ pending |
| 03-04-02 | 04 | 2 | TEST-04 | — | N/A | unit | `uv run pytest tests/unit/test_external/test_data_service.py -x` | N (add) | ⬜ pending |
| 03-05-01 | 05 | 2 | TEST-04, TEST-01 | — | N/A | unit | `uv run pytest tests/unit/test_utils/ -x` | N (create) | ⬜ pending |
| 03-05-02 | 05 | 2 | TEST-04 | — | N/A | unit | `uv run pytest tests/unit/test_utils/test_cache_utils.py -x` | Y (extend) | ⬜ pending |
| 03-05-03 | 05 | 2 | TEST-04 | — | N/A | unit | `uv run pytest tests/unit/test_services/test_narrative_service.py -x` | Y (extend) | ⬜ pending |
| 03-06-01 | 06 | 3 | TEST-05 | — | Separate test DB | integration | `uv run pytest tests/integration/test_risk_api_e2e.py -x` | N (create) | ⬜ pending |
| 03-06-02 | 06 | 3 | TEST-05 | — | Separate test DB | integration | `uv run pytest tests/integration/test_valuation_api_e2e.py -x` | N (create) | ⬜ pending |
| 03-06-03 | 06 | 3 | TEST-05 | — | Separate test DB | integration | `uv run pytest tests/integration/test_yield_api_e2e.py -x` | N (create) | ⬜ pending |
| 03-07-01 | 07 | 3 | TEST-06 | — | Parameterized queries | integration | `uv run pytest tests/integration/test_repositories.py -x` | N (create) | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/unit/test_utils/test_validators.py` — stubs for TEST-04 (validators.py 0% coverage)
- [ ] `tests/integration/conftest.py` — shared DB fixtures (test engine, session factory, table creation)
- [ ] `tests/integration/test_repositories.py` — repository CRUD tests
- [ ] `tests/integration/test_risk_api_e2e.py` — risk API E2E tests
- [ ] `tests/integration/test_valuation_api_e2e.py` — valuation API E2E tests
- [ ] `tests/integration/test_yield_api_e2e.py` — yield API E2E tests
- [ ] PostgreSQL on localhost:5433 with `stockvaluefinder_test` database created

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL database availability on localhost:5433 | TEST-05, TEST-06 | Infrastructure dependency | Verify `psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE stockvaluefinder_test"` succeeds |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
