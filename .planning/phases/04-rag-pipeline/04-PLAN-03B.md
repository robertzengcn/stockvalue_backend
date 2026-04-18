---
wave: 3
depends_on: [04-01, 04-01B, 04-02, 04-03]
files_modified:
  - stockvaluefinder/api/documents_routes.py
  - stockvaluefinder/api/dependencies.py
  - stockvaluefinder/main.py
must_haves:
  truths:
    - Document upload endpoint accepts PDF files and returns status
    - Document search endpoint returns parent-child pairs with page references
    - Qdrant health check integrated into startup
    - Document routes registered in main.py
  artifacts:
    - stockvaluefinder/api/documents_routes.py
    - stockvaluefinder/api/dependencies.py (get_qdrant_client, check_qdrant_health)
    - stockvaluefinder/main.py (route registration, health check)
  key_links:
    - documents_routes uses DocumentService and SemanticRetriever
    - dependencies provides get_qdrant_client for routes
    - main.py registers documents_router and adds Qdrant health check
requirements: DATA-03, DATA-07
---

# Phase 4 Plan 03B: Document API Routes

**Goal:** Create document upload/search endpoints and integrate with FastAPI.

## Tasks

<Task id="04-03B-01">
<action>Create document routes in api/documents_routes.py with endpoints: POST /api/v1/documents/upload (accepts file: UploadFile, ticker: str, year: int, report_type: str, returns DocumentUploadResponse), GET /api/v1/documents/{document_id}/status (returns document status), POST /api/v1/documents/search (accepts DocumentSearchRequest, returns list of SearchResult with parent context), DELETE /api/v1/documents/{document_id} (deletes document). Validate file is PDF, validate ticker format, sanitize filename, use BackgroundTasks for async processing</action>
<read_first>
- stockvaluefinder/api/risk_routes.py (API endpoint pattern)
- stockvaluefinder/api/stock_helpers.py (validation helpers)
- stockvaluefinder/models/document.py (request/response models)
- stockvaluefinder/services/document_service.py (service interface)
</read_first>
<acceptance_criteria>
- documents_routes.py exists with router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
- POST /upload validates file ends with .pdf, ticker matches regex, file size < 100MB
- POST /upload uses BackgroundTasks to call document_service.process_upload asynchronously
- POST /upload returns ApiResponse with DocumentUploadResponse
- GET /{document_id}/status returns current processing status
- POST /search accepts DocumentSearchRequest, returns list of SearchResult with parent_content
- DELETE /{document_id} removes document from Qdrant and database
- mypy passes: `uv run mypy stockvaluefinder/api/documents_routes.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run pytest tests/unit/test_api/test_documents_routes.py -x -q</automated>
</verify>
<done>
- All 4 endpoints implemented
- Validation and async processing working
- mypy and tests pass
</done>
</Task>

<Task id="04-03B-02">
<action>Add Qdrant dependency in api/dependencies.py: create get_qdrant_client() returning QdrantVectorStore instance, initialized with config values. Add health check function check_qdrant_health() returning bool, used in lifespan for startup verification</action>
<read_first>
- stockvaluefinder/api/dependencies.py (existing dependency pattern)
- stockvaluefinder/config.py (RAGConfig)
- stockvaluefinder/rag/vector_store.py (QdrantVectorStore)
</read_first>
<acceptance_criteria>
- dependencies.py exports `get_qdrant_client() -> QdrantVectorStore`
- dependencies.py exports `check_qdrant_health() -> bool`
- get_qdrant_client initializes QdrantVectorStore with url, collection, api_key from RAGConfig
- check_qdrant_health returns True if Qdrant connection succeeds, False otherwise
- mypy passes: `uv run mypy stockvaluefinder/api/dependencies.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run mypy stockvaluefinder/api/dependencies.py</automated>
</verify>
<done>
- get_qdrant_client and check_qdrant_health implemented
- mypy passes
</done>
</Task>

<Task id="04-03B-03">
<action>Register document routes in main.py: add `app.include_router(documents_router)` alongside existing routers, add Qdrant health check to lifespan startup (graceful degradation if Qdrant unavailable)</action>
<read_first>
- stockvaluefinder/main.py (router registration pattern, lifespan)
- stockvaluefinder/api/documents_routes.py (new router)
</read_first>
<acceptance_criteria>
- main.py imports `from stockvaluefinder.api.documents_routes import router as documents_router`
- main.py contains `app.include_router(documents_router)`
- lifespan function checks Qdrant health via check_qdrant_health()
- If Qdrant unavailable, app starts with warning log (does not crash)
- main.py passes mypy: `uv run mypy stockvaluefinder/main.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run pytest tests/unit/test_main_lifespan.py -x -q</automated>
</verify>
<done>
- documents_router registered
- Qdrant health check in lifespan
- mypy and tests pass
</done>
</Task>

<Task id="04-03B-04">
<action>Add optional document_ids parameter to existing analysis endpoints: modify POST /api/v1/analyze/risk and POST /api/v1/analyze/dcf to accept optional document_ids: list[str] parameter, when provided, use SemanticRetriever to fetch document context and augment analysis with retrieved passages</action>
<read_first>
- stockvaluefinder/api/risk_routes.py (risk endpoint)
- stockvaluefinder/api/valuation_routes.py (valuation endpoint)
- stockvaluefinder/rag/retriever.py (SemanticRetriever)
</read_first>
<acceptance_criteria>
- risk_routes.py POST /analyze/risk accepts optional document_ids: list[str] = Query(None)
- valuation_routes.py POST /analyze/dcf accepts optional document_ids: list[str] = Query(None)
- When document_ids provided, endpoint calls SemanticRetriever.search() to fetch context
- Retrieved passages included in analysis result (added to response model)
- mypy passes: `uv run mypy stockvaluefinder/api/risk_routes.py stockvaluefinder/api/valuation_routes.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run pytest tests/unit/test_api/test_risk_routes.py tests/unit/test_api/test_valuation_routes.py -x -q</automated>
</verify>
<done>
- document_ids parameter added to both endpoints
- SemanticRetriever integrated
- mypy and tests pass
</done>
</Task>

## Verification

After completing this wave:
- [ ] `uv run pytest tests/unit/test_api/test_documents_routes.py tests/unit/test_services/test_document_service.py -x -q` exits 0
- [ ] `uv run pytest tests/integration/test_rag_e2e.py -x -q` exits 0 (requires Qdrant running)
- [ ] `uv run mypy stockvaluefinder/api/documents_routes.py stockvaluefinder/services/document_service.py stockvaluefinder/api/dependencies.py stockvaluefinder/main.py` exits 0
- [ ] Server starts: `uv run uvicorn stockvaluefinder.main:app --reload` connects to Qdrant

## Threat Model

| Threat | STRIDE | Mitigation | Implemented In |
|--------|--------|------------|----------------|
| Path traversal via filename | Tampering | Sanitize filename, use UUID-based storage paths | Task 04-03B-01 (filename validation) |
| DoS via large file upload | Denial of Service | File size limit (100MB), request timeout, background processing | Task 04-03B-01 (size check, BackgroundTasks) |
| Unauthorized document access | Access Control | Validate ticker format, optionally add auth later | Task 04-03B-01 (ticker validation) |
