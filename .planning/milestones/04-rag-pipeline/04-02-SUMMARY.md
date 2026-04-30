---
phase: 04-rag-pipeline
plan: 02
subsystem: rag
tags: [qdrant, bge-m3, embeddings, pdf, pymupdf, retrieval, multi-query-expansion]

# Dependency graph
requires:
  - phase: 04-01
    provides: RAGConfig frozen dataclass, ChunkMetadata/DocumentChunk models
  - phase: 04-01B
    provides: DocumentDB ORM model, DocumentRepository, documents table migration

provides:
  - PDF processor with parent-child chunking and table preservation
  - BGE-M3 embedding client via OpenRouter API with retry/backoff
  - Qdrant vector store with filtered search and payload indexes
  - Semantic retriever with LLM-powered multi-query expansion
  - SearchResult frozen dataclass for structured retrieval output

affects: [04-rag-pipeline, document-service, analysis-endpoints]

# Tech tracking
tech-stack:
  added: [pymupdf, bge-m3-via-openrouter, qdrant-vector-store, semantic-retriever]
  patterns: [parent-child-document-retrieval, multi-query-expansion, frozen-search-result]

key-files:
  created:
    - stockvaluefinder/rag/pdf_processor.py
    - stockvaluefinder/rag/embeddings.py
    - stockvaluefinder/rag/vector_store.py
    - stockvaluefinder/rag/retriever.py
    - tests/unit/test_rag/test_pdf_processor.py
    - tests/unit/test_rag/test_embeddings.py
    - tests/unit/test_rag/test_vector_store.py
    - tests/unit/test_rag/test_retriever.py
  modified:
    - stockvaluefinder/rag/__init__.py

key-decisions:
  - "PyMuPDF for PDF parsing with find_tables() for table detection and markdown export"
  - "OpenRouter as bge-m3 embedding API provider via httpx.AsyncClient with retry/backoff"
  - "Single Qdrant collection annual_reports with metadata filtering instead of per-stock collections"
  - "LLM-powered multi-query expansion with graceful fallback to basic search"
  - "Parent content fetched from Qdrant search by parent_id, not from PostgreSQL (simpler for MVP)"

patterns-established:
  - "Frozen dataclass SearchResult for immutable search results"
  - "Lazy LLM initialization with graceful degradation pattern (from NarrativeService)"
  - "Deduplication by chunk_id keeping highest score for multi-query aggregation"
  - "Filter builder pattern for Qdrant metadata filtering"

requirements-completed: [DATA-04, DATA-05, DATA-06, DATA-07]

# Metrics
duration: 13min
completed: 2026-04-19
---

# Phase 4 Plan 02: RAG Core Modules Summary

**PDF processor with PyMuPDF parent-child chunking, bge-m3 embedding client via OpenRouter, Qdrant vector store with filtered search, and semantic retriever with LLM-powered multi-query expansion**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-18T22:34:50Z
- **Completed:** 2026-04-19T00:08:12Z
- **Tasks:** 4 (3 previously completed + 1 this session)
- **Files modified:** 10

## Accomplishments
- PDF processor extracts structured content with page references, table preservation via PyMuPDF find_tables()
- BGE-M3 embedding client generates 1024-dim vectors via OpenRouter API with batch processing and retry logic
- Qdrant vector store manages collection with COSINE distance, payload indexes, and filtered search
- Semantic retriever with multi-query expansion via LLM, deduplication, and parent context fetching

## Task Commits

Each task was committed atomically:

1. **Task 04-02-01: PDF processor** - `d9b6b6d` (feat)
2. **Task 04-02-02: BGE-M3 embedding client** - `a642716` (feat)
3. **Task 04-02-03: Qdrant vector store** - `c7515d5` (feat)
4. **Task 04-02-04: Semantic retriever** - `ef196fb` (feat)

## Files Created/Modified
- `stockvaluefinder/rag/pdf_processor.py` - PDF parsing with PyMuPDF, parent-child chunking, table detection
- `stockvaluefinder/rag/embeddings.py` - BGEEmbeddingClient via OpenRouter API with retry logic
- `stockvaluefinder/rag/vector_store.py` - QdrantVectorStore with collection management and filtered search
- `stockvaluefinder/rag/retriever.py` - SemanticRetriever with search, multi-query expansion, parent context
- `tests/unit/test_rag/test_pdf_processor.py` - PDF processor unit tests
- `tests/unit/test_rag/test_embeddings.py` - Embedding client unit tests
- `tests/unit/test_rag/test_vector_store.py` - Vector store unit tests
- `tests/unit/test_rag/test_retriever.py` - Retriever unit tests (18 tests)

## Decisions Made
- Used lazy LLM initialization pattern from NarrativeService for multi-query expansion, with graceful fallback to basic search when LLM unavailable
- Parent context fetched from Qdrant search by parent_id rather than PostgreSQL (simpler for MVP, avoids cross-service dependency in retriever)
- SearchResult is a frozen dataclass following the established ChunkMetadata/DocumentChunk pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing _deduplicate_results method**
- **Found during:** Task 04-02-04 (Semantic Retriever)
- **Issue:** Initial implementation referenced self._deduplicate_results() but the method was not defined
- **Fix:** Added static _deduplicate_results method that tracks best score per chunk_id using a dict
- **Files modified:** stockvaluefinder/rag/retriever.py
- **Verification:** All 18 tests pass including deduplication tests
- **Committed in:** ef196fb (Task 04-02-04 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor implementation oversight caught by tests. No scope creep.

## Issues Encountered
None - all four tasks implemented cleanly following established patterns.

## User Setup Required
None - no external service configuration required for this plan. Qdrant Docker and OpenRouter API key are needed for runtime but already documented in 04-RESEARCH.md.

## Next Phase Readiness
- All four RAG core modules (PDF processor, embeddings, vector store, retriever) are complete
- Ready for Plan 04-03: Document service orchestration and API endpoints
- The retriever's multi-query expansion depends on LLM availability (graceful degradation implemented)

---
*Phase: 04-rag-pipeline*
*Completed: 2026-04-19*
