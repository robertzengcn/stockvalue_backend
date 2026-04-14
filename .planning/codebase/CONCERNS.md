# Codebase Concerns & Issues

## Technical Debt

### Incomplete Implementations
- **calculation_sandbox.py**: Entire file is a TODO stub (line 25: `raise NotImplementedError`)
- **agents/ (all 4 files)**: coordinator, risk, valuation, yield agents are scaffolding
- **rag/ (all 4 files)**: vector_store, retriever, embeddings, pdf_processor are scaffolding
- **main.py lifespan**: 5 TODOs for DB/Redis/Qdrant initialization and shutdown (lines 31-37)

### TODO/FIXME Comments
- `calculation_sandbox.py:5-9`: TODO for Docker-based sandbox implementation
- `calculation_sandbox.py:25`: TODO for Docker container execution
- `main.py:31-37`: TODO comments for startup/shutdown initialization

### Hardcoded Values
- `narrative_service.py:42`: Hardcoded `provider="deepseek"` should use config
- `db/base.py:17`: Hardcoded database URL with credentials in source code (SECURITY ISSUE)
- `rate_client.py:16-28`: Static fallback rates hardcoded in module

## Architecture Concerns

### Route Fatigue (God Routes)
- `valuation_routes.py` (296 lines): Handles price fetching, rate fetching, valuation, narrative, DB save, stock name lookup
- `risk_routes.py` (149 lines): Fetches 2 years of data, analyzes, generates narrative, saves to DB
- `yield_routes.py` (183 lines): Fetches prices/yields/rates, analyzes, generates narrative, saves to DB
- **Recommendation**: Extract "analysis orchestrator" layer between routes and services

### Missing Abstractions
- No "analysis orchestrator" to coordinate: data fetch -> calculate -> narrative -> save
- No result caching: same stock analyzed multiple times fetches data each time
- No rate limiting on external API calls

### Circular Reference Risk
- `main.py:112-114`: `_rebuild_forward_refs()` needed to resolve circular imports between model files
- Indicates potential circular dependency between valuation models

## Security Concerns

### CRITICAL: Hardcoded Database Credentials
- `db/base.py:17`: `postgresql+asyncpg://svf_admin:Fo41_2vhaOHKnBAyMUToMA@localhost:5433/stockvaluefinder`
- **Password exposed in source code**: `Fo41_2vhaOHKnBAyMUToMA`
- Should ONLY use environment variable, no hardcoded fallback

### API Key Handling
- `llm_config.py:133-140`: API keys read from env vars (acceptable)
- No validation that API keys are non-empty before use (empty string accepted for local models)

### Input Validation
- Ticker validation: regex `^\d{6}\.(SH|SZ|HK)$` on route requests (good)
- Financial data from external sources: minimal validation before calculations
- No rate limiting on API endpoints

### Error Message Leakage
- `risk_routes.py:142`: Error messages somewhat generic (good)
- `valuation_routes.py:201`: Returns raw validation error message to client
- Log messages include ticker symbols (acceptable)

## Performance Concerns

### No Caching of External Data
- `CacheManager` implemented but **never used** in routes or services
- Same stock's financial report fetched from external API on every request
- Could cache: financial reports (24h TTL), stock prices (5min TTL), rates (1h TTL)

### Sequential External Calls (Partially Addressed)
- `valuation_routes.py:61-72`: Good - uses `asyncio.gather` for parallel data fetches
- `yield_routes.py:84-90`: Good - uses `asyncio.gather` for parallel data fetches
- `risk_routes.py:71-80`: BAD - fetches current and previous reports sequentially

### N+1 Query Risk
- Routes create new `RateClient()` per request (no connection pooling for rate client)
- `RateClient.__init__` creates httpx.AsyncClient without reuse

### Large File
- `data_service.py` at ~1187 lines exceeds 800-line guideline
- Contains 6 mock data methods that could be extracted

## Data Quality Concerns

### M-Score Indices Default Values
- `data_service.py:875-882` (AKShare), `952-959` (efinance), `1021-1030` (Tushare):
  All 8 Beneish M-Score indices are hardcoded to 1.0/0.0 defaults
- **These are never actually calculated from raw financial data**
- The M-Score calculation in `risk_service.py` uses whatever values are in the dict
- This means M-Score results are meaningless until index calculation is implemented

### Field Name Fragility
- `data_service.py:552-573`: Tries multiple field names (English + Chinese) for each metric
- If AKShare/efinance API changes field names silently, data extraction fails
- No schema validation on external API responses

### FCF Calculation Accuracy
- `data_service.py:576`: `fcf = ocf - abs(capex)` assumes capex is positive
- `data_service.py:607`: `fcf = ocf + capex` assumes capex is negative (Tushare convention)
- Different conventions between data sources may cause inconsistencies

## Testing Concerns

### Low Coverage Areas
- **Risk service**: M-Score, F-Score, 存贷双高 detection - core business logic untested
- **API routes**: Zero integration tests
- **Repositories**: Zero database operation tests
- **Narrative service**: Zero LLM integration tests
- **Rate client**: Zero tests for rate fetching
- **Cache manager**: Zero tests for Redis operations

### Missing Test Infrastructure
- No test database fixture (in-memory SQLite or testcontainers PostgreSQL)
- No mock HTTP server for external API testing
- No test fixtures for financial data

## Missing Features (Defined in Docs, Not Implemented)

1. **M-Score Index Calculation**: Only the formula is implemented, the 8 indices are never calculated from raw financial data
2. **RAG Pipeline**: Qdrant, embeddings, PDF processing, document retrieval - all scaffolding
3. **LLM Agents**: LangGraph-based agents for coordinated analysis - scaffolding
4. **Calculation Sandbox**: Docker-based isolated Python execution - TODO
5. **Redis Caching**: CacheManager implemented but never integrated
6. **Historical Rate Data**: `rate_client.py:289` placeholder implementation
7. **HK Rate Fetching**: Static rates only, HKMA API pending
8. **Semantic Conflict Check**: MD&A vs. auditor opinion inconsistency detection
9. **Batch Report Generation**: Static reports for CSI 300 (MVP requirement)

## Recommendations (Priority Order)

1. **CRITICAL**: Remove hardcoded database credentials from `db/base.py:17`
2. **HIGH**: Implement actual M-Score index calculation from raw financial data
3. **HIGH**: Add tests for risk service (M-Score, F-Score, 存贷双高)
4. **HIGH**: Integrate Redis caching for external data (financial reports, prices)
5. **MEDIUM**: Extract route orchestration logic to reduce route complexity
6. **MEDIUM**: Add API integration tests with test database
7. **MEDIUM**: Make narrative provider configurable instead of hardcoded
8. **LOW**: Implement RAG pipeline and LLM agents
9. **LOW**: Add rate limiting to API endpoints
10. **LOW**: Implement calculation sandbox for isolated Python execution
