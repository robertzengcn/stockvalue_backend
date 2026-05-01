# Phase 7: Report Processing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 07-report-processing
**Areas discussed:** PDF Download Strategy, Partial Failure Handling, Financial Data for Analyzers, Analysis Orchestration

---

## PDF Download Strategy

| Question | Options | Selected |
|----------|---------|----------|
| PDF URL source | AKShare links / Construct CNInfo URLs / Skip PDF, use structured data | ✓ AKShare provides PDF links |
| File storage structure | Subdirectories by stock/year / Flat UPLOAD_DIR with UUID | ✓ Subdirectories by stock/year |

**Notes:** AKShare disclosure functions return PDF links in metadata. Store in organized directory structure for easy browsing.

---

## Partial Failure Handling

| Question | Options | Selected |
|----------|---------|----------|
| Failure state | New ANALYZING_PARTIAL / FAILED with partial results / Block until all succeed | ✓ FAILED with partial results |
| Result storage | JSON in result_summary / Separate analysis_results table | ✓ JSON in result_summary |

**Notes:** Keep state machine simple (no new state). Store per-analyzer status in result_summary JSON. Successful results persist even when task state is FAILED.

---

## Financial Data for Analyzers

| Question | Options | Selected |
|----------|---------|----------|
| Data source | AKShare structured / Extract from PDF via RAG/LLM / AKShare + RAG fallback | ✓ AKShare primary + RAG fallback |
| Years to fetch | 2 years current+previous / All available | ✓ 2 years (current + previous) |

**Notes:** AKShare provides exact structured data analyzers need. RAG fallback for resilience when AKShare is unavailable.

---

## Analysis Orchestration

| Question | Options | Selected |
|----------|---------|----------|
| Analyzer execution | Parallel asyncio.gather / Sequential / Separate arq jobs | ✓ Parallel via asyncio.gather |
| Per-ticker uniqueness | arq job uniqueness / Redis lock / No enforcement | ✓ arq _unique_key_infunc |
| Analysis job structure | Single analyze_report job / Two-phase fetch+analyze | ✓ Single job |

**Notes:** asyncio.gather for parallelism within one job. arq handles dedup. Single job keeps pipeline simple.

---

## Claude's Discretion

- AKShare PDF download URL extraction method
- Financial data mapping to analyzer input format
- PDF extraction fallback implementation
- Error formatting for partial failures
- Retry logic within asyncio.gather

## Deferred Ideas

- OCR fallback for scanned PDFs (PaddleOCR) — future milestone
- Incremental RAG updates — future
- Detailed processing audit trail — future
