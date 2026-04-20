---
status: testing
phase: 04-rag-pipeline
source: 04-01-SUMMARY.md, 04-01B-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-03B-SUMMARY.md
started: 2026-04-19T10:00:00Z
updated: 2026-04-19T10:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Cold Start Smoke Test
expected: |
  Start the FastAPI server from scratch. Server boots without errors, Qdrant health check runs during lifespan startup (gracefully degrades if Qdrant not available), and the /docs page loads showing all registered routes including the new /api/v1/documents endpoints.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Start the FastAPI server from scratch. Server boots without errors, Qdrant health check runs during lifespan startup (gracefully degrades if Qdrant not available), and the /docs page loads showing all registered routes including the new /api/v1/documents endpoints.
result: [pending]

### 2. PDF Upload Endpoint
expected: POST /api/v1/documents/upload with a PDF file and ticker (e.g., "600519.SH") returns ApiResponse with success=True, containing a document_id and status="processing". Response confirms the file was accepted for background processing.
result: [pending]

### 3. Upload Status Polling
expected: GET /api/v1/documents/status/{document_id} returns the document's processing status. Status transitions from "processing" to "completed" after PDF is parsed, chunked, embedded, and stored. A "failed" status is shown if processing encounters an error.
result: [pending]

### 4. Semantic Search Endpoint
expected: POST /api/v1/documents/search with a query (e.g., "revenue growth") and ticker filter returns ranked search results. Each result includes the passage text, relevance score, source page number, and parent document context.
result: [pending]

### 5. Document Deletion
expected: DELETE /api/v1/documents/{document_id} removes the document from both PostgreSQL and Qdrant. Returns success confirmation. Subsequent GET /status/{id} returns 404 or indicates document no longer exists.
result: [pending]

### 6. Parent-Document Retrieval
expected: Semantic search returns 2000-token parent context passages, not just 500-token child chunks. When a child chunk matches the query, the full parent document section is returned with the child's relevance score.
result: [pending]

### 7. Metadata Filtering on Search
expected: Search results can be filtered by metadata fields (ticker, year). POST /api/v1/documents/search with ticker="600519.SH" only returns results from that stock's documents, not from other tickers.
result: [pending]

### 8. RAG Context on Risk Analysis
expected: POST /api/v1/analyze/risk with ticker and document_ids parameter includes document-derived context in the response meta field. Risk analysis is enriched with passages from the uploaded annual report.
result: [pending]

### 9. RAG Context on DCF Valuation
expected: POST /api/v1/analyze/dcf with ticker and document_ids parameter includes document-derived context in the response. DCF valuation is enriched with relevant passages from uploaded documents.
result: [pending]

### 10. Qdrant Graceful Degradation
expected: When Qdrant is unavailable (not running), the server still starts and responds to non-document API calls normally. Document-related endpoints return appropriate error messages. Existing risk/valuation/yield endpoints continue to work without RAG context.
result: [pending]

### 11. File Size Validation
expected: Uploading a file larger than 100MB returns an error response (413 or 400) with a clear message about the size limit. No processing is attempted on oversized files.
result: [pending]

### 12. Phase 4 Unit Tests Pass
expected: Running `uv run pytest tests/unit/test_rag/ tests/unit/test_services/test_document_service.py tests/unit/test_api/test_documents_routes.py tests/unit/test_api/test_dependencies.py -v` shows all tests passing with no failures or errors.
result: [pending]

## Summary

total: 12
passed: 0
issues: 0
pending: 12
skipped: 0
blocked: 0

## Gaps

[none yet]
