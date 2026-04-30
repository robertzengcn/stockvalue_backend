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

- Phase 03 (Test Coverage) took 116min across 6 plans — the E2E integration tests (03-05) alone took 80min due to pytest marker setup, mypy fixes, and DB fixture configuration
- Some plans had rework from pre-existing bugs discovered during testing (lifespan tests, broken test assertions)
- ROADMAP progress table wasn't kept in sync with actual execution status
- REQUIREMENTS.md checkboxes weren't updated as phases completed (had to reconcile from SUMMARY.md files at milestone close)

### Patterns Established

- **Graceful degradation** as a core pattern for all optional infrastructure (Redis, Qdrant, LLM)
- **Frozen config dataclasses** with singleton pattern via lru_cache
- **ApiResponse[T] meta field** for extending responses without breaking schema
- **BackgroundTasks for async processing** with immediate status response
- **skip_if_no_db pytest marker** for optional integration tests
- **Versioned cache keys** with v1 prefix for safe cache invalidation

### Key Lessons

1. **Integration tests are expensive but essential** — the 80min spent on E2E tests caught real bugs in dependency injection, middleware, and DB session handling
2. **External API field names are unstable** — always use multi-level fallback with Chinese field name as secondary
3. **Cache serialization needs explicit handling** — UUID and Decimal types don't serialize to JSON by default
4. **Vector DB APIs change between versions** — mock the client interface, not the specific method signatures
5. **Update tracking docs as you go** — reconciling REQUIREMENTS.md at milestone close is error-prone

### Cost Observations

- Model mix: Primarily Sonnet-class for implementation, Opus for planning/decisions
- Total plans: 15 across 63 days
- Average plan duration: 16min
- Notable: Phase 03 took disproportionately long due to infrastructure setup (pytest markers, test DB, conftest)
- Notable: Phase 04 was efficient (65min for 5 plans) due to established patterns from earlier phases

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 4 |
| Plans | 15 |
| Avg plan duration | 16min |
| Total execution time | ~4h |
| LOC delivered | 24,057 |
| Test coverage | 80%+ |
| Bugs found in testing | 12 |
| Timeline | 63 days |
