# Phase 4: RAG Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** 04-rag-pipeline
**Areas discussed:** PDF Upload & Processing, Embedding & Vector Store, Retrieval & API Design, Integration with Existing Analysis

---

## PDF Upload & Processing

### Upload format

| Option | Description | Selected |
|--------|-------------|----------|
| Multipart form-data | Standard file upload with `POST /api/v1/documents/upload` | ✓ |
| Base64 in JSON body | Send PDF as base64 string in JSON payload | |

**User's choice:** Multipart form-data with file upload
**Notes:** Standard FastAPI pattern, browser-friendly, works with curl/Postman easily.

### Table handling

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve tables intact | Keep tables whole even if they exceed 500 tokens | ✓ |
| Split tables normally | Treat tables like any other text | |
| Hybrid approach | Preserve small tables, split large ones with headers | |

**User's choice:** Preserve tables intact
**Notes:** Critical for accuracy, creates uneven chunk sizes but maintains data integrity.

### Extraction depth

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text only | Strip all formatting, just raw text | |
| Text + table structure | Preserve table grids as markdown/HTML | |
| Full structure with page refs | Preserve headers, sections, tables, AND page numbers | ✓ |

**User's choice:** Full structure with page references
**Notes:** Required to satisfy "source page reference" success criterion.

---

## Embedding & Vector Store

### bge-m3 deployment

| Option | Description | Selected |
|--------|-------------|----------|
| Local model | Run via sentence-transformers on server | |
| API version | Use via API provider (Together AI, Anyscale) | ✓ |

**User's choice:** API version
**Notes:** Reduces infrastructure complexity, no GPU requirements, per-call costs acceptable for MVP single-user scale.

### Qdrant setup

| Option | Description | Selected |
|--------|-------------|----------|
| Self-hosted Docker | Run Qdrant in Docker alongside app | ✓ |
| Cloud-hosted | Use Qdrant Cloud (managed service) | |

**User's choice:** Self-hosted Docker
**Notes:** Aligns with existing Docker-based architecture, full control, no per-query costs.

### Metadata schema

| Option | Description | Selected |
|--------|-------------|----------|
| Basics only | ticker, year, report type | |
| Extended | ticker, year, report type, company name, filing date, document section | ✓ |

**User's choice:** Extended (6 fields)
**Notes:** Enables flexible filtering and temporal queries.

---

## Retrieval & API Design

### Response format

| Option | Description | Selected |
|--------|-------------|----------|
| Parent documents only | Return 2000-token parent context | |
| Child + parent pairing | Return matched child with parent context attached | ✓ |
| Ranked snippets | Top-N ranked passages with scores | |

**User's choice:** Child + parent pairing
**Notes:** Precise matches with full context.

### Result limiting

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed limit | Always return top N results | |
| Score threshold | Return all results above threshold | |
| Hybrid | Both fixed limit AND score threshold | ✓ |

**User's choice:** Hybrid approach
**Notes:** Balances quality and quantity control.

### Query expansion

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, multi-query | Generate 3-5 query variations, aggregate results | ✓ |
| No, single query | Direct search with exact query | |
| Optional flag | `expand_query` parameter per-request | |

**User's choice:** Multi-query expansion enabled by default
**Notes:** Better recall for financial document search.

---

## Integration with Existing Analysis

### Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone endpoints | Separate upload and search endpoints | |
| Integrated into analysis | Add `document_id` to existing analysis endpoints | |
| Hybrid | Both standalone + optional document_ids in analysis | ✓ |

**User's choice:** Hybrid approach
**Notes:** Standalone `/api/v1/documents/upload` and `/api/v1/documents/search`, plus optional `document_ids` parameter in existing analysis endpoints.

### Document linking

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, required | Ticker must be provided at upload | ✓ |
| Yes, optional | Ticker can be provided but isn't required | |
| No linking | Extract ticker from PDF content | |

**User's choice:** Ticker required at upload time
**Notes:** Creates explicit relationships in database, enables "get all documents for this stock" queries.

### Auto-trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, auto-trigger | Upload → process → auto-run analyses | |
| No, manual trigger | Upload and analysis are separate | ✓ |
| Optional flag | `run_analysis` parameter at upload | |

**User's choice:** No, manual trigger only
**Notes:** Upload and analysis are separate operations. Users explicitly request analysis after upload.

---

## Claude's Discretion

The following areas were left to Claude's discretion:
- Specific API endpoint paths and request/response schemas
- bge-m3 API provider choice (Together AI, Anyscale, or other)
- Qdrant collection configuration (vector dimensions, distance metric)
- Chunking algorithm details (token counting method, table detection heuristics)
- Multi-query expansion prompt design and result deduplication strategy
- Relevance score threshold and result limit default values

## Deferred Ideas

None — discussion stayed within phase scope.
