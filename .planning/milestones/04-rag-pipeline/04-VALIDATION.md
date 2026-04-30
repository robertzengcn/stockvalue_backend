---
phase: 4
slug: rag-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0+ with pytest-asyncio |
| **Config file** | `stockvaluefinder/pyproject.toml` (tool.pytest) |
| **Quick run command** | `uv run pytest tests/unit/test_rag/ tests/unit/test_api/test_documents_routes.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x --cov=stockvaluefinder --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_rag/ tests/unit/test_api/test_documents_routes.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x --cov=stockvaluefinder --cov-report=term-missing`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DATA-03 | T-04-01 | Filename sanitized, UUID storage path | unit | `uv run pytest tests/unit/test_api/test_documents_routes.py::test_upload_pdf -x` | W0 | pending |
| 04-01-02 | 01 | 1 | DATA-03 | T-04-02 | File type validation, size limit | unit | `uv run pytest tests/unit/test_api/test_documents_routes.py::test_upload_rejects_non_pdf -x` | W0 | pending |
| 04-02-01 | 02 | 1 | DATA-04 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_chunking_token_counts -x` | W0 | pending |
| 04-02-02 | 02 | 1 | DATA-04 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_table_preservation -x` | W0 | pending |
| 04-02-03 | 02 | 1 | DATA-04 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_page_references -x` | W0 | pending |
| 04-02-04 | 02 | 1 | DATA-05 | T-04-03 | API key from env var, not logged | unit | `uv run pytest tests/unit/test_rag/test_embeddings.py::test_embedding_dimensions -x` | W0 | pending |
| 04-02-05 | 02 | 1 | DATA-05 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_embeddings.py::test_batch_embedding -x` | W0 | pending |
| 04-03-01 | 03 | 2 | DATA-06 | — | N/A | integration | `uv run pytest tests/integration/test_rag_vector_store.py::test_upsert_and_search -x` | W0 | pending |
| 04-03-02 | 03 | 2 | DATA-06 | — | N/A | integration | `uv run pytest tests/integration/test_rag_vector_store.py::test_filtered_search -x` | W0 | pending |
| 04-03-03 | 03 | 2 | DATA-07 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_parent_child_retrieval -x` | W0 | pending |
| 04-03-04 | 03 | 2 | DATA-07 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_page_reference_in_results -x` | W0 | pending |
| 04-03-05 | 03 | 2 | DATA-07 | — | N/A | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_score_threshold -x` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_rag/test_pdf_processor.py` -- stubs for DATA-04
- [ ] `tests/unit/test_rag/test_embeddings.py` -- stubs for DATA-05
- [ ] `tests/unit/test_rag/test_retriever.py` -- stubs for DATA-07
- [ ] `tests/unit/test_api/test_documents_routes.py` -- stubs for DATA-03
- [ ] `tests/integration/test_rag_vector_store.py` -- stubs for DATA-06
- [ ] PyMuPDF install: `uv add pymupdf` -- required before any PDF test

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chinese annual report PDF text extraction quality | DATA-04 | Requires real PDF file and visual inspection | Upload a real Chinese annual report PDF and verify extracted text is readable |
| bge-m3 embedding quality for Chinese financial terms | DATA-05 | Requires semantic similarity judgment | Search for Chinese financial terms and verify relevant passages are returned |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] nyquist_compliant: true set in frontmatter

**Approval:** pending
