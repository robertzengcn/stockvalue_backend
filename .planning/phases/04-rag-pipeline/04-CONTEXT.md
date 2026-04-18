# Phase 4: RAG Pipeline - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a complete RAG pipeline for processing annual report PDFs: upload endpoint (multipart form-data), PDF parsing with full structure preservation (tables intact, page references), bge-m3 embeddings via API, Qdrant vector storage (self-hosted Docker), and semantic retrieval with child+parent pairing. Documents are linked to specific stocks (ticker required), metadata includes ticker/year/report type/company name/filing date/section. Search supports multi-query expansion with hybrid result limiting. Standalone document endpoints plus optional document augmentation in analysis endpoints. Manual analysis trigger (no auto-trigger).

Scope: PDF upload, chunking (500-token children, 2000-token parents), bge-m3 embedding generation, Qdrant integration, semantic search endpoint, document-stock relationship in database. Does NOT include: auto-triggering analysis after upload, agent orchestration (Phase 5), or calculation sandbox (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### PDF Upload & Processing

- **D-01:** Upload format — Multipart form-data with file upload (`POST /api/v1/documents/upload` with `file: UploadFile`). Standard FastAPI pattern, browser-friendly, works with curl/Postman.
- **D-02:** Table handling — Preserve financial tables intact even if they exceed 500-token chunk size. Critical for accuracy, creates uneven chunk sizes but maintains data integrity.
- **D-03:** Extraction depth — Full structure with page references. Preserve headers, sections, tables, AND track original page numbers for every chunk to satisfy "source page reference" requirement.

### Embedding & Vector Store

- **D-04:** bge-m3 deployment — API version (not local model). Reduces infrastructure complexity, no GPU requirements, per-call costs acceptable for MVP single-user scale.
- **D-05:** Qdrant setup — Self-hosted Docker. Aligns with existing Docker-based architecture, full control, no per-query costs, matches CLAUDE.md specifications.
- **D-06:** Metadata schema — Index 6 fields: ticker, year, report type, company name, filing date, document section. Enables flexible filtering and temporal queries.

### Retrieval & API Design

- **D-07:** Response format — Child + parent pairing. Return matched 500-token child document with its 2000-token parent context attached. Precise matches with full context.
- **D-08:** Result limiting — Hybrid approach: return up to N results (e.g., 10) that exceed relevance score threshold (e.g., >0.7). Balances quality and quantity control.
- **D-09:** Query expansion — Multi-query expansion enabled by default. Generate 3-5 query variations using LLM, search each, aggregate and deduplicate results. Better recall for financial document search.

### Integration with Existing Analysis

- **D-10:** Architecture — Hybrid approach. Standalone `/api/v1/documents/upload` and `/api/v1/documents/search` endpoints, plus optional `document_ids` parameter in existing analysis endpoints (`/api/v1/analyze/risk`, `/api/v1/analyze/dcf`) for document-augmented analysis.
- **D-11:** Document linking — Ticker required at upload time. Creates explicit relationships in database, enables "get all documents for this stock" queries.
- **D-12:** Auto-trigger — No, manual trigger only. Upload and analysis are separate operations. Users explicitly request analysis after upload.

### Claude's Discretion

- Specific API endpoint paths and request/response schemas
- bge-m3 API provider choice (Together AI, Anyscale, or other)
- Qdrant collection configuration (vector dimensions, distance metric)
- Chunking algorithm details (token counting method, table detection heuristics)
- Multi-query expansion prompt design and result deduplication strategy
- Relevance score threshold and result limit default values

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §DATA-03 to DATA-07 — RAG pipeline requirements and traceability
- `.planning/ROADMAP.md` §Phase 4 — Phase goal and success criteria

### Existing codebase
- `stockvaluefinder/stockvaluefinder/rag/` — Current RAG scaffolding (vector_store.py, retriever.py, embeddings.py, pdf_processor.py — all TODO stubs)
- `stockvaluefinder/stockvaluefinder/api/risk_routes.py` — Example API endpoint pattern for reference
- `stockvaluefinder/stockvaluefinder/api/dependencies.py` — Dependency injection patterns (get_db, get_initialized_data_service)
- `stockvaluefinder/stockvaluefinder/db/models/` — Database models for document-stock relationships

### Database models
- `stockvaluefinder/stockvaluefinder/db/models/stock.py` — Stock model (for document linking)
- `stockvaluefinder/stockvaluefinder/db/models/financial.py` — Financial report model (potential relationship)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- FastAPI `UploadFile` type — Standard file upload handling in `api/` layer
- Existing API endpoint patterns — `risk_routes.py`, `valuation_routes.py`, `yield_routes.py` show consistent REST design
- Dependency injection — `get_db()` for database sessions, can extend with `get_qdrant_client()`
- SQLAlchemy ORM models — Document models can follow existing patterns (frozen Pydantic models, JSONB columns for metadata)

### Established Patterns
- API response envelope — `ApiResponse[T]` with `success`, `data`, `error` fields
- Async database sessions — `AsyncSession` with proper transaction handling
- Error handling — Custom exception hierarchy (`StockValueFinderError` → `DataValidationError`, `ExternalAPIError`)
- Singleton service pattern — `ExternalDataService` with lazy initialization

### Integration Points
- Database: Need new `documents` table with fields for file_path, ticker (FK), metadata (JSONB), processing_status
- Qdrant: Need collection per stock or global collection with ticker filter (design choice for planning)
- API routes: New `documents_routes.py` to be registered in `main.py`
- Existing analysis routes: Add optional `document_ids` parameter to risk/valuation/yield endpoints

</code_context>

<specifics>
## Specific Ideas

- PDF processing library: Consider `pymupdf` (fitz) for fast PDF text extraction with page/structure preservation, or `pdfplumber` for better table detection
- Token counting: Use `tiktoken` with appropriate encoding (cl100k_base for bge-m3 compatibility)
- Table detection: Use PDF structure (column spans, row alignment) or OCR-based table extraction for complex tables
- Page reference format: Store as `{"page": 12, "bbox": [x1, y1, x2, y2]}` for precise location tracking
- bge-m3 API: Together AI offers bge-m3 at $0.10 per 1M tokens, reasonable for MVP scale

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-rag-pipeline*
*Context gathered: 2026-04-18*
