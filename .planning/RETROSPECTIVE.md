# Retrospective: StockValueFinder

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-01
**Phases:** 4 | **Plans:** 15

### What Was Built

1. Real Beneish M-Score calculation with 8 computed indices and per-index audit trail (replaced hardcoded defaults)
2. Redis caching for all external data methods with TTL, versioned keys, graceful degradation
3. Comprehensive test suite: 100+ tests, 80%+ coverage, PostgreSQL-backed E2E integration tests
4. Full RAG pipeline: PDF upload → parent-child chunking → bge-m3 embeddings → Qdrant vector search → semantic retrieval with document API routes

### What Worked

- **Frozen dataclasses/Pydantic models** for configuration and audit trail ensured immutability and caught errors early
- **Graceful degradation pattern** (Redis, Qdrant, LLM) kept the system functional even when optional services are unavailable
- **Test-first approach within phases** caught bugs immediately (M-Score data issues, cache serialization, vector store API changes)
- **Phased delivery** — each phase built on the previous, no circular dependencies
- **Multi-source field mapping fallback** handled the messy reality of AKShare/efinance field name instability

### What Was Inefficient

- Phase 03 (Test Coverage) took 116min across 6 plans — the E2E integration tests (03-05) alone took 80min
- Some plans had rework from pre-existing bugs discovered during testing
- ROADMAP progress table wasn't kept in sync with actual execution status
- REQUIREMENTS.md checkboxes weren't updated as phases completed

### Patterns Established

- **Graceful degradation** as a core pattern for all optional infrastructure
- **Frozen config dataclasses** with singleton pattern via lru_cache
- **ApiResponse[T] meta field** for extending responses without breaking schema
- **BackgroundTasks for async processing** with immediate status response
- **skip_if_no_db pytest marker** for optional integration tests
- **Versioned cache keys** with v1 prefix for safe cache invalidation

### Key Lessons

1. Integration tests are expensive but essential
2. External API field names are unstable — always use multi-level fallback
3. Cache serialization needs explicit handling for UUID and Decimal types
4. Vector DB APIs change between versions — mock the client interface
5. Update tracking docs as you go — reconciling at milestone close is error-prone

### Cost Observations

- Model mix: Primarily Sonnet-class for implementation, Opus for planning/decisions
- Total plans: 15 across 63 days
- Average plan duration: 16min

---

## Milestone: v1.2 — Alpha Engine V2.0

**Shipped:** 2026-05-07
**Phases:** 4 | **Plans:** 12

### What Was Built

1. ROIC-WACC spread analysis with sector-aware NOPAT, true WACC with debt weighting, and 3-year moat trend via scipy regression
2. Capital Allocation scorecard (buyback yield, DPU stability via linregress, blind expansion detection, combined A/B/C/D grade)
3. Policy Resonance Engine (PDF upload to Qdrant policy_documents, vector similarity matching, LLM verification, DCF terminal growth adjustment)
4. Composite Alpha score with fixed 40/30/20/10 weights, dimension-specific normalization, AlphaLevel classification, and full audit trail

### What Worked

- **Wave-based 3-plan pattern** (pure functions → data layer → API wiring) is highly repeatable — all 4 phases followed it successfully
- **Direct route handler function calls** for orchestration endpoints avoided HTTP self-call overhead and ASGI deadlock risk
- **Plan checker** caught 2 blockers before Phase 12 execution (missing __init__.py registration, unresolved RESEARCH.md questions)
- **scipy integration** for trend line regression was clean — well-tested, lightweight dependency
- **TDD approach** with RED/GREEN commits in Plan 01 ensured calculation correctness before data/API integration
- **Established patterns** (repository upsert, frozen configs, non-blocking persistence) meant Plans 02-03 executed in 2-3 min each

### What Was Inefficient

- Phase 11 (Policy Resonance) took 45 min — the longest phase — due to LLM helper integration and Qdrant cross-collection search complexity
- REQUIREMENTS.md traceability table was stale (phases 9-11 not checked off despite UAT passing)
- v1.1 retrospective section was skipped during v1.1 close — had to infer from archives
- Plan checker found clerical issues (unresolved open questions in RESEARCH.md) that should have been caught during planning

### Patterns Established

- **Orchestration endpoint pattern**: POST endpoint calling multiple route handlers directly, extracting fields, normalizing, computing composite
- **Non-blocking persistence**: DB errors logged but API response returned — analysis result is primary
- **Dimension-specific normalization**: Each analysis dimension maps to 0-100 via domain-appropriate methods (linear clamp, grade map, pass-through, tier map)
- **Lazy import with Any fallback**: For repository imports that may not be available during parallel execution

### Key Lessons

1. **Plan checker is worth the 2-min overhead** — caught missing __init__.py wiring and stale research questions before execution
2. **Direct function calls beat HTTP self-call** for orchestration — simpler, faster, no ASGI deadlock risk
3. **IEEE 754 precision matters** — ROIC-WACC normalization needed round(..., 2) to handle floating point edge cases
4. **stock_individual_info_em() does NOT return business descriptions** — verified the hard way, use stock_profile_cninfo() instead
5. **Phase execution speed increases as patterns solidify** — Phase 12 took 8 min total vs Phase 11's 45 min

### Cost Observations

- Model mix: Sonnet-class for execution, Opus for planning/decisions
- Total execution time: 87 min across 12 plans
- Average plan duration: 7 min (Phase 12: ~3 min, Phase 11: ~15 min)
- Notable: Execution speed doubled from Phase 11 to Phase 12 due to established patterns

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 | v1.2 |
|--------|------|------|------|
| Phases | 4 | 4 | 4 |
| Plans | 15 | 12 | 12 |
| Avg plan duration | 16min | ~12min | 7min |
| Total execution time | ~4h | ~2.5h | 87min |
| LOC delivered | 24,057 | ~18,000 | 8,547 (app) |
| Test coverage | 80%+ | 80%+ | 80%+ |
| UAT tests passed | N/A | N/A | 20/20 |
| Timeline | 63 days | 1 day | 4 days |
| New dependencies | redis, qdrant | arq, APScheduler | scipy |

**Velocity trend:** Accelerating — from 16min/plan (v1.0) to 7min/plan (v1.2), largely due to pattern reuse.
