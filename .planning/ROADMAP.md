# Roadmap: StockValueFinder

## Overview

Fix the broken M-Score fraud detection by calculating real indices from actual financial data, then layer on caching for performance, build the RAG pipeline for annual report analysis, and finally orchestrate everything through a multi-agent system. Tests accompany each phase rather than being a separate phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: M-Score Real Calculation** - Fix hardcoded M-Score indices by calculating all 8 from actual financial data with data validation
- [ ] **Phase 2: Redis Cache Integration** - Wire existing CacheManager into all routes and services with TTL policies and cache key versioning
- [ ] **Phase 3: Test Coverage** - Achieve 80%+ coverage across all services and API endpoints with unit and integration tests
- [ ] **Phase 4: RAG Pipeline** - Build PDF upload, chunking, bge-m3 embedding, Qdrant storage, and semantic retrieval for annual reports
- [ ] **Phase 5: Multi-Agent Orchestration** - Implement LangGraph state machine with coordinator agent orchestrating parallel risk/valuation/yield analysis
- [ ] **Phase 6: Analysis Persistence Integration** - Wire agent pipeline output through to database persistence with structured analysis output and narrative summaries

## Phase Details

### Phase 1: M-Score Real Calculation
**Goal**: Users receive accurate M-Score fraud detection results calculated from actual financial data, not hardcoded defaults
**Depends on**: Nothing (first phase)
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06, RISK-07, RISK-08, RISK-09, RISK-10
**Success Criteria** (what must be TRUE):
  1. Risk API returns M-Score where each of the 8 component indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) reflects actual year-over-year financial data for any CSI 300 stock
  2. Risk API response includes a breakdown of each individual index value alongside the composite M-Score, with data source references indicating which financial fields were used
  3. M-Score values differ meaningfully across stocks (not clustered around a single default value), matching manual calculation for a known test stock (600519.SH)
  4. Missing or unavailable financial fields produce explicit data validation errors rather than silently defaulting to 0.0
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Extend data_service field mappings, MScoreData model with audit trail, remove hardcoded indices (Wave 1)
- [x] 01-02-PLAN.md — Implement calculate_mscore_indices function and wire into analyze_financial_risk (Wave 2, depends on 01-01)

### Phase 2: Redis Cache Integration
**Goal**: External data responses are served from Redis cache with appropriate TTLs, reducing API latency and protecting upstream rate limits
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. Repeated requests for the same stock's financial data within 24 hours return cached responses without hitting AKShare/efinance upstream APIs
  2. Stock price data is cached for 5 minutes and interest rate data for 1 hour, with distinct cache keys per ticker, year, and data type
  3. Cache responses include a `cached_at` timestamp so consumers know data freshness
  4. Cache miss on fresh data still works correctly, fetching from upstream and populating cache
**Plans**: TBD

Plans:
- [x] 02-01: TBD
- [x] 02-02: TBD

### Phase 3: Test Coverage
**Goal**: All core services and API endpoints have 80%+ test coverage with both unit and integration tests, ensuring correctness of financial calculations
**Depends on**: Phase 1, Phase 2
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. `uv run pytest --cov=stockvaluefinder` reports 80%+ coverage for risk_service, valuation_service, yield_service, and data_service
  2. Unit tests verify M-Score index calculations, DCF valuation math, yield gap formulas, and data fallback logic with known inputs and expected outputs
  3. Integration tests exercise risk, valuation, and yield API endpoints end-to-end with mocked external services, confirming correct request/response behavior
  4. Integration tests verify database CRUD operations (create, read) for analysis results using test database fixtures
**Plans**: 6 plans

Plans:
- [x] 03-01-PLAN.md — Shared factory fixtures + risk_service tests (Wave 1, TEST-01)
- [x] 03-02-PLAN.md — Valuation + yield service tests (Wave 1, TEST-02, TEST-03)
- [x] 03-03-PLAN.md — Data service fallback and normalization tests (Wave 2, TEST-04)
- [x] 03-04-PLAN.md — Validators, cache, narrative tests (Wave 2, TEST-04)
- [x] 03-05-PLAN.md — API integration tests with test database (Wave 3, TEST-05)
- [ ] 03-06-PLAN.md — Repository integration tests (Wave 3, TEST-06)

### Phase 4: RAG Pipeline
**Goal**: Users can upload annual report PDFs and retrieve semantically relevant passages with source page references, enabling document-backed analysis
**Depends on**: Phase 2
**Requirements**: DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):
  1. User can upload a PDF annual report via API endpoint and receive confirmation that it was processed and indexed
  2. Uploaded PDF is chunked into 500-token child documents and 2000-token parent documents, with financial tables preserved as complete units
  3. Semantic search endpoint returns parent-document context passages ranked by relevance, filtered by metadata (ticker, year, report type)
  4. Each retrieved passage includes source page reference linking back to the original PDF
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

### Phase 5: Multi-Agent Orchestration
**Goal**: A single API request triggers coordinated parallel analysis across risk, valuation, and yield domains, producing a comprehensive analysis result
**Depends on**: Phase 3, Phase 4
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05
**Success Criteria** (what must be TRUE):
  1. POST /api/v1/analyze/comprehensive accepts a ticker and returns combined risk + valuation + yield analysis in a single response
  2. Coordinator agent dispatches analysis to risk, valuation, and yield agent nodes which each produce results matching their standalone API counterparts
  3. Agent pipeline uses LangGraph state machine with typed state, and agent nodes call existing deterministic calculation services (not LLM arithmetic)
  4. Analysis results from the comprehensive endpoint are consistent with results from individual risk/valuation/yield endpoints for the same stock
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: Analysis Persistence Integration
**Goal**: Comprehensive analysis results are persisted to PostgreSQL with structured output and LLM-generated narrative summaries
**Depends on**: Phase 5
**Requirements**: AGENT-06
**Success Criteria** (what must be TRUE):
  1. Comprehensive analysis results are stored in PostgreSQL and can be retrieved by ticker and date without re-computation
  2. Stored results include a Chinese-language narrative summary generated by the LLM that accurately reflects the deterministic calculation results
  3. Narrative summary does not contradict the numerical analysis results (validation step catches mismatches)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. M-Score Real Calculation | 0/2 | Planning complete | - |
| 2. Redis Cache Integration | 0/2 | Not started | - |
| 3. Test Coverage | 0/6 | Planning complete | - |
| 4. RAG Pipeline | 0/3 | Not started | - |
| 5. Multi-Agent Orchestration | 0/3 | Not started | - |
| 6. Analysis Persistence Integration | 0/2 | Not started | - |
