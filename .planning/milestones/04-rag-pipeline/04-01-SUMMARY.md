---
phase: 04-rag-pipeline
plan: 01
subsystem: infra
tags: [pymupdf, pdf, rag, qdrant, bge-m3, config]

# Dependency graph
requires: []
provides:
  - pymupdf installed and importable for PDF processing
  - RAGConfig frozen dataclass with all RAG pipeline settings
  - rag_config singleton exported from config.py
affects: [04-rag-pipeline]

# Tech tracking
tech-stack:
  added: [pymupdf>=1.27.2.2]
  patterns: [frozen dataclass config, singleton export]

key-files:
  created: []
  modified:
    - stockvaluefinder/pyproject.toml
    - stockvaluefinder/uv.lock
    - stockvaluefinder/stockvaluefinder/config.py

key-decisions:
  - "RAGConfig uses frozen dataclass pattern matching existing config conventions"
  - "All 16 RAG fields have sensible defaults matching research recommendations"

patterns-established:
  - "RAGConfig follows existing frozen dataclass + singleton pattern from ValuationConfig/RiskConfig"

requirements-completed: [DATA-03, DATA-06]

# Metrics
duration: 13min
completed: 2026-04-18
---

# Phase 4 Plan 01: Dependencies & Configuration Summary

**PyMuPDF installed for PDF parsing and RAGConfig frozen dataclass added with 16 fields for Qdrant, embedding, chunking, search, and file storage settings**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-18T12:53:34Z
- **Completed:** 2026-04-18T13:06:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Installed PyMuPDF v1.27.2.2 for PDF text extraction with table detection and CJK support
- Added RAGConfig frozen dataclass with all 16 configuration fields (Qdrant connection, embedding API, chunking parameters, search settings, file storage)
- Exported rag_config singleton following existing project conventions

## Task Commits

Each task was committed atomically:

1. **Task 04-01-01: Install PyMuPDF dependency** - `19d9a1a` (feat)
2. **Task 04-01-02: Add RAGConfig dataclass** - `ae7787b` (feat)

## Files Created/Modified
- `stockvaluefinder/pyproject.toml` - Added pymupdf>=1.27.2.2 dependency
- `stockvaluefinder/uv.lock` - Updated lockfile with pymupdf transitive dependencies
- `stockvaluefinder/stockvaluefinder/config.py` - Added RAGConfig class and rag_config singleton

## Decisions Made
- RAGConfig placed alongside existing config classes (ValuationConfig, RiskConfig, etc.) in config.py for consistency
- All 16 fields have sensible defaults matching research recommendations: bge-m3 via OpenRouter, 1024-dim vectors, 500-token child / 2000-token parent chunking, COSINE distance with 0.7 score threshold
- API key referenced via env var name (EMBEDDING_API_KEY_ENV) rather than reading directly, matching existing pattern where env vars are read at point-of-use

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-commit hook's ruff-format ran on an unstaged test file from a previous phase, requiring the formatting fix to be included in Task 01's commit. No functional impact.

## User Setup Required
None - no external service configuration required for this plan.

## Next Phase Readiness
- pymupdf is available for PDF processing tasks in subsequent plans
- RAGConfig provides all default values needed by pdf_processor.py, embeddings.py, vector_store.py, and retriever.py
- Plans 04-02 and 04-03 can now reference `from stockvaluefinder.config import rag_config`

## Self-Check: PASSED

All files exist: pyproject.toml, uv.lock, config.py, 04-01-SUMMARY.md
All commits found: 19d9a1a, ae7787b

---
*Phase: 04-rag-pipeline*
*Completed: 2026-04-18*
