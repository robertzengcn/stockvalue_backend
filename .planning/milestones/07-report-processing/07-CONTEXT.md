# Phase 7: Report Processing - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

## Phase Boundary

Downloaded reports are parsed, embedded into Qdrant, and analyzed by existing risk/valuation/yield services — with deduplication preventing redundant work and partial failure handled gracefully. This phase implements the 3 worker stubs (download_report, parse_report, analyze_report) from Phase 5 as fully functional processing steps.

## Implementation Decisions

### PDF Download Strategy

- **D-01:** AKShare disclosure functions provide PDF download links as part of announcement metadata. Use these links directly — no manual CNInfo URL construction needed.
- **D-02:** Store PDFs in UPLOAD_DIR with subdirectory structure: `./uploads/{ticker}/{fiscal_year}/{report_type}/`. Organized by stock for easy browsing and manual inspection.
- **D-03:** Use existing request_delay_seconds (0.5s) from PipelineConfig for rate limiting between downloads.

### Partial Failure Handling

- **D-04:** Keep existing DONE/FAILED states only. If any analyzer fails, task goes to FAILED with error details. Successful results are still persisted. No new ANALYZING_PARTIAL state.
- **D-05:** Store partial analysis results in pipeline_tasks.result_summary as JSON with per-analyzer status (e.g., `{"risk": {"status": "success", "result_ref": "..."}, "valuation": {"status": "failed", "error": "..."}}`). Error message lists which failed and why.

### Financial Data for Analyzers

- **D-06:** Primary source: fetch structured financial statements from AKShare/efinance using ticker + fiscal_year. These provide exact data analyzers need in structured format.
- **D-07:** Fallback: extract financial data from parsed PDF text via RAG/LLM if AKShare fails. Less reliable but provides resilience.
- **D-08:** Fetch 2 years of financial data (current + previous) for comparison. Analyzers like M-Score need consecutive years. Store in existing financial_reports table.

### Analysis Orchestration

- **D-09:** Run all 3 analyzers (risk, valuation, yield) in parallel within the analyze_report job using asyncio.gather with exception handling. Fastest approach since analyzers are independent.
- **D-10:** Enforce per-ticker job uniqueness via arq's _unique_key_infunc pattern. If another job for the same ticker is running, it waits or is deduplicated.
- **D-11:** Single analyze_report job handles: fetch financials → run analyzers in parallel → store results → transition state. No split into fetch + analyze phases.

### Claude's Discretion

- Exact AKShare method for PDF download links from disclosure data
- Financial data mapping from AKShare response to analyzer input format
- PDF extraction fallback implementation details
- Error message formatting for partial failures
- Retry logic for individual analyzer failures within asyncio.gather

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §PIPE — PIPE-01, PIPE-02, PIPE-03, PIPE-07, PIPE-08, PIPE-09, PIPE-10

### Prior Phase Context
- `.planning/phases/05-pipeline-foundation/05-CONTEXT.md` — Pipeline infrastructure decisions
- `.planning/phases/05-pipeline-foundation/05-02-SUMMARY.md` — Worker stubs, state machine, repo
- `.planning/phases/06-smart-watcher/06-CONTEXT.md` — Watcher service, disclosure metadata
- `.planning/phases/06-smart-watcher/06-02-SUMMARY.md` — WatcherService, AKShare disclosure methods

### Existing Code (Critical)
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` — Worker stubs to implement
- `stockvaluefinder/stockvaluefinder/pipeline/repo.py` — transition_state(), create_task()
- `stockvaluefinder/stockvaluefinder/pipeline/state.py` — State machine transitions
- `stockvaluefinder/stockvaluefinder/pipeline/config.py` — PipelineConfig fields
- `stockvaluefinder/stockvaluefinder/services/document_service.py` — process_upload() for RAG
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` — analyze_financial_risk()
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` — DCF calculation functions
- `stockvaluefinder/stockvaluefinder/services/yield_service.py` — Yield calculation functions
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — Financial data methods

## Existing Code Insights

### Reusable Assets

- **Worker stubs**: `download_report`, `parse_report`, `analyze_report` in worker.py — replace logging with real implementation
- **DocumentService.process_upload()**: Full RAG pipeline (PDF → chunks → embed → Qdrant). Signature: `(document_id, ticker, file_name, file_path, pdf_bytes)`
- **Analysis services**: RiskAnalyzer, DCFValuationService, YieldAnalyzer all accept structured financial data dicts
- **PipelineConfig**: request_delay_seconds=0.5, max_concurrent_tasks=5, max_retries=3, retry_delays=(2.0, 8.0, 30.0)
- **PipelineTaskRepository**: transition_state() with SELECT FOR UPDATE, create_task() with business_key
- **AKShareClient**: Already has get_profit_sheet(), get_balance_sheet(), get_cash_flow_sheet() methods

### Integration Points

- **worker.py**: Replace 3 stub functions with real implementations
- **pipeline/repo.py**: transition_state() drives state machine for each processing step
- **pipeline/config.py**: May need new fields for storage paths
- **services/**: Call existing services — no modifications needed to analysis services
- **external/akshare_client.py**: May need PDF download URL extraction method

## Deferred Ideas

- OCR fallback for scanned PDFs (PaddleOCR) — future milestone
- Incremental RAG updates — update only affected chunks — future
- Processing audit trail with detailed step timing — future
- Batch CSI 300 screening — future

---

*Phase: 07-report-processing*
*Context gathered: 2026-05-01*
