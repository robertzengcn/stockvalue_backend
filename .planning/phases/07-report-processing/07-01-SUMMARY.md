---
phase: "07-report-processing"
plan: "01"
subsystem: "pipeline-download"
tags: ["download-worker", "document-repository", "pdf-download", "deduplication", "tdd"]
dependency_graph:
  requires: ["Phase 5 pipeline foundation", "Phase 6 watcher service"]
  provides: ["PipelineDocumentRepository", "download_report worker", "_extract_pdf_url", "_download_pdf", "_get_source_metadata", "_enqueue_parse"]
  affects: ["worker.py"]
tech_stack:
  added: ["httpx streaming", "hashlib.sha256", "pathlib.Path"]
  patterns: ["streaming download with incremental SHA256", "3-tier deduplication", "CNInfo PDF URL extraction from announcementId"]
key_files:
  created:
    - "stockvaluefinder/stockvaluefinder/pipeline/document_repo.py"
    - "stockvaluefinder/tests/unit/test_pipeline/test_document_repo.py"
    - "stockvaluefinder/tests/unit/test_pipeline/test_download_worker.py"
  modified:
    - "stockvaluefinder/stockvaluefinder/pipeline/worker.py"
    - "stockvaluefinder/tests/unit/test_pipeline/test_worker.py"
    - "stockvaluefinder/.gitignore"
decisions:
  - "Used urllib.parse to extract announcementId from CNInfo detail URL for PDF download URL construction"
  - "Content-Type validation rejects HTML responses to prevent processing error pages as PDFs"
  - "Deduplication at application level -- content_hash not enforced by unique constraint"
  - "Patched pathlib.Path.write_bytes in tests instead of builtins.open (matches actual code)"
metrics:
  duration: "20 minutes"
  completed: "2026-05-02"
  tasks: 2
  files_created: 3
  files_modified: 3
  tests_added: 26
  tests_passing: 356
---

# Phase 7 Plan 01: Download Report Worker Summary

PipelineDocumentRepository and functional download_report worker replacing the Phase 5 stub with PDF download, SHA256 hashing, filesystem storage, 3-tier deduplication, rate limiting, state machine transitions, and parse_report job enqueue.

## What Was Built

### Task 1: PipelineDocumentRepository

Created `stockvaluefinder/stockvaluefinder/pipeline/document_repo.py` with 4 methods:

- **create_document**: Inserts a PipelineDocumentDB record with all metadata fields (task_id, source_url, source_id, content_hash, file_path, file_size, downloaded_at). Uses uuid4() for document_id and utcnow for downloaded_at.
- **get_by_content_hash**: Returns matching document by SHA256 content hash for deduplication.
- **get_by_source_id**: Returns matching document by announcement ID for deduplication.
- **get_by_task_id**: Returns matching document by pipeline task ID.

10 unit tests in `test_document_repo.py` covering all methods and dedup behavior.

### Task 2: download_report Worker

Replaced the stub in `worker.py` with a fully functional implementation:

- **_extract_pdf_url**: Parses announcementId from the CNInfo detail URL stored in pending_disclosures.source_raw, constructs `https://static.cninfo.com.cn/{announcementId}.PDF`.
- **_download_pdf**: Streams PDF via httpx AsyncClient with configurable rate limiting (asyncio.sleep), validates Content-Type is PDF or octet-stream (rejects HTML), computes SHA256 hash incrementally from 8KB chunks.
- **_get_source_metadata**: Queries pending_disclosures by parsing business_key (ticker:fiscal_year:report_type) to find the disclosure record and extract source_id and source_raw.
- **_enqueue_parse**: Creates a temporary Redis connection via arq create_pool and enqueues parse_report with per-task _job_id for uniqueness.
- **download_report**: Orchestrates the full flow -- load task, transition to DOWNLOADING, get source metadata, extract PDF URL, check source_id dedup, download PDF, check content_hash dedup, write to filesystem at `UPLOAD_DIR/{ticker}/{fiscal_year}/{report_type}/{source_id}.pdf`, create document record, transition to PARSING, commit, enqueue parse.

16 unit tests in `test_download_worker.py` covering all behaviors from the plan: successful download state transitions, document creation with SHA256, rate limiting, source_id dedup, content_hash dedup, failure transition, HTML rejection, early return on missing task, and parse enqueue.

### Additional Changes

- Updated the old `test_download_report_runs_without_error` stub test in `test_worker.py` to work with the new function signature (provides mock session_factory and PipelineTaskRepository).
- Added `uploads/` to `.gitignore` to prevent test artifacts from being tracked.

## Commits

| Commit | Message |
|--------|---------|
| `203dd8c` | feat(07-01): implement PipelineDocumentRepository with CRUD operations |
| `aff45a2` | feat(07-01): implement download_report worker with PDF download pipeline |
| `6809173` | fix(07-01): patch file I/O in tests and add uploads/ to gitignore |

## Verification Results

- All 356 pipeline tests pass (`uv run pytest stockvaluefinder/tests/unit/test_pipeline/ -v`)
- Linting clean: `ruff check` passes on both modules
- Formatting clean: `ruff format --check` passes on both modules
- No accidental file deletions in any commit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test stub compatibility break**
- **Found during:** Task 2 verification
- **Issue:** Old `test_download_report_runs_without_error` test called download_report with empty ctx dict, but the new implementation requires `session_factory` in ctx.
- **Fix:** Updated the test to provide mock session_factory and PipelineTaskRepository, verifying that the function returns early when the task is not found (matching the new behavior).
- **Files modified:** `stockvaluefinder/tests/unit/test_pipeline/test_worker.py`
- **Commit:** `aff45a2`

**2. [Rule 3 - Blocking] Test file I/O leaked to filesystem**
- **Found during:** Task 2 verification
- **Issue:** Some tests did not mock file I/O operations, causing actual directories and files to be created in the uploads/ directory during test runs.
- **Fix:** Added `patch("pathlib.Path.mkdir")` and `patch("pathlib.Path.write_bytes")` to all tests that exercise the download_report happy path. Added `uploads/` to `.gitignore`.
- **Files modified:** `test_download_worker.py`, `.gitignore`
- **Commit:** `6809173`

## Threat Flags

No new security-relevant surface introduced beyond what was in the threat model. Content-Type validation (T-07-01 mitigation) is implemented in `_download_pdf`. Path traversal (T-07-02) is mitigated by ticker validation from PipelineTaskCreate regex. URL domain validation (T-07-03) is inherent in the static URL construction pattern.

## Known Stubs

None. Both tasks are fully implemented with no placeholder values.

## Self-Check: PASSED

- FOUND: 203dd8c (PipelineDocumentRepository)
- FOUND: aff45a2 (download_report worker)
- FOUND: 6809173 (test fixes)
- FOUND: document_repo.py
- FOUND: worker.py
- FOUND: test_document_repo.py
- FOUND: test_download_worker.py
- 356 pipeline tests passing
