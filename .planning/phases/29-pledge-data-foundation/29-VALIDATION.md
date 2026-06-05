---
phase: 29
slug: pledge-data-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-asyncio |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/unit/test_external/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_external/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 | DATA-01 | T-29-01 | Input validation on ticker codes | unit | `uv run pytest tests/unit/test_utils/test_validators.py -k normalize -x` | W0 | pending |
| 29-01-02 | 01 | 1 | DATA-02 | — | Pydantic model validation | unit | `uv run pytest tests/unit/test_models/test_equity_pledge.py -x` | W0 | pending |
| 29-01-03 | 01 | 1 | DATA-03 | — | Field mapping correctness | unit | `uv run pytest tests/unit/test_external/test_akshare_client.py -k pledge -x` | W0 | pending |
| 29-02-01 | 02 | 2 | DATA-04 | — | Cache key format and TTL | unit | `uv run pytest tests/unit/test_external/test_data_service.py -k pledge -x` | W0 | pending |
| 29-02-02 | 02 | 2 | DATA-05 | — | Date discovery logic | unit | `uv run pytest tests/unit/test_external/test_data_service.py -k date_discovery -x` | W0 | pending |
| 29-02-03 | 02 | 2 | DATA-06 | T-29-02 | External API error handling | unit | `uv run pytest tests/unit/test_external/test_akshare_client.py -k pledge_error -x` | W0 | pending |
| 29-02-04 | 02 | 2 | DATA-07 | — | Tushare fallback activation | unit | `uv run pytest tests/unit/test_external/test_data_service.py -k tushare_fallback -x` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_utils/test_validators.py` — stubs for normalize_a_share_ticker
- [ ] `tests/unit/test_models/test_equity_pledge.py` — stubs for EquityPledgeSnapshot, EquityPledgeDetail
- [ ] `tests/unit/test_external/test_akshare_client.py` — stubs for pledge methods
- [ ] `tests/unit/test_external/test_data_service.py` — stubs for pledge interfaces

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real AKShare live fetch returns valid pledge data | DATA-01 | Requires live API access, non-deterministic | Manually call with a known ticker (600519) |
| Redis cache TTL expires correctly after 24h | DATA-04 | TTL verification requires time wait | Check Redis key TTL via `redis-cli TTL <key>` after initial fetch |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
