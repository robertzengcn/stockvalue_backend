# PRD: Market Scanner CLI

**Version**: V1.0  
**Date**: 2026-06-05  
**Target Directory**: `stockvalue_backend/doc`  
**Product**: StockValueFinder  

---

## 1. Product Background

StockValueFinder already includes a market scanner that can identify stocks with attractive value characteristics inside index pools such as CSI300 and CSI500. The scanner currently has backend components for orchestration, ARQ worker execution, REST API triggering, scan run persistence, candidate result queries, and watchlist integration.

The current workflow is still backend/API oriented. A developer or operator must either call REST endpoints manually or interact with worker code directly. This creates friction for common operational tasks such as starting a scan, checking the latest scan status, listing candidates, exporting results, or adding a candidate to the watchlist.

This PRD proposes a first-class command line interface for market scanner operations. The CLI should make it easy to find high-value, low-price stock candidates from the terminal while reusing the existing scanner implementation and preserving the same data model and business rules.

---

## 2. Product Goal

### 2.1 Core Goal

Provide a CLI that allows users and operators to start market scans, monitor scan results, inspect candidates, and promote candidates into the watchlist without writing ad hoc scripts or manually calling HTTP endpoints.

### 2.2 Product Principle

The CLI must be an operational interface over the existing scanner. It must not create a separate screening engine or duplicate valuation logic.

### 2.3 Definition of "High Value but Low Price"

In this product, "low price" does not mean low nominal share price. It means current market price appears low relative to estimated business value.

The CLI should expose scanner results that are based on:

- Margin of safety from DCF valuation
- Composite value score
- Low PE/PB and valuation percentile signals
- Dividend/yield gap support
- Acceptable financial risk profile
- Cash flow and quality filters
- Explainable candidate reasons and risk flags

---

## 3. Target Users

### 3.1 Primary Users

- Project operators who run scans manually or through scheduled jobs
- Developers validating scanner behavior during local development
- Power users who prefer terminal workflows for investment research

### 3.2 Secondary Users

- CI/CD or automation jobs that need machine-readable scan outputs
- Analysts who want to export candidate lists for downstream review

---

## 4. User Problems

- Starting a scan requires knowledge of backend internals or API request shape.
- Checking whether a scan completed requires manual database/API inspection.
- Candidate results are hard to review quickly from the terminal.
- There is no simple JSON output for automation.
- Redis/ARQ may be unavailable in local development, but users still need a direct scan path.
- Operators need clear error messages when backend services, database, Redis, or data providers are unavailable.

---

## 5. Scope

### 5.1 In Scope for V1

V1 must support:

- Starting a scan through the backend API and ARQ queue
- Running a scan directly from the CLI for local/development usage
- Listing recent scan runs
- Showing latest scan status for an index
- Listing scan candidates
- Showing one candidate detail
- Adding a candidate to the watchlist
- Human-readable Rich table output
- JSON output for scripts and automation
- Configurable API base URL and authentication token
- Clear exit codes for success, command/config errors, and scan/API failures

### 5.2 Out of Scope for V1

V1 does not need to support:

- A new stock screening algorithm
- Interactive terminal UI
- Portfolio management
- Buy/sell recommendations
- Real-time intraday signal generation
- Full-market scanning beyond scanner-supported index pools
- Editing scanner rules from the CLI
- User account registration/login flows, except accepting an existing token

---

## 6. Product Workflows

### 6.1 Start a Queued Scan

User starts a scan through the backend API:

```bash
stockvalue scan start --index CSI300 --index CSI500 --type daily --top-n 50
```

Expected behavior:

- CLI sends a request to `POST /api/v1/scanner/runs`.
- Backend enqueues `run_market_scan` in ARQ.
- CLI prints job id and queued status.
- If Redis/worker is unavailable, CLI shows a clear failure message.

### 6.2 Run a Direct Local Scan

User runs a scan without API/ARQ:

```bash
stockvalue scan run --index CSI300 --type weekly --top-n 100 --direct
```

Expected behavior:

- CLI reuses the existing `run_market_scan` function.
- CLI requires database and data-provider configuration.
- CLI prints completed/failed status and scan metadata.
- CLI does not bypass scanner rules or create alternate calculations.

### 6.3 Show Latest Scan

```bash
stockvalue scan latest --index CSI300
```

Expected behavior:

- CLI shows latest run id, status, scan type, counts, started time, completed time, and rules version.
- JSON mode returns the raw response in stable machine-readable shape.

### 6.4 List Candidates

```bash
stockvalue scan candidates --latest --index CSI300 --limit 20
```

Expected behavior:

- CLI shows candidates ranked by composite score or persisted rank order.
- Output includes ticker, index, score, margin of safety, intrinsic value, risk level, and created time when available.

### 6.5 Inspect Candidate Detail

```bash
stockvalue scan candidate <candidate-id>
```

Expected behavior:

- CLI prints detailed valuation, scoring, reasons, risk flags, and scan provenance.
- JSON mode includes the complete candidate payload.

### 6.6 Add Candidate to Watchlist

```bash
stockvalue scan watchlist-add <candidate-id>
```

Expected behavior:

- CLI calls the existing backend watchlist integration endpoint.
- If the stock already exists in the watchlist, CLI reports that no duplicate was created.
- If successful, the stock becomes part of the existing watchlist workflow.

---

## 7. Command Surface

### 7.1 Recommended Commands

```bash
stockvalue scan start
stockvalue scan run
stockvalue scan runs
stockvalue scan latest
stockvalue scan candidates
stockvalue scan candidate
stockvalue scan watchlist-add
```

### 7.2 Global Options

```bash
--api-url TEXT       Backend API base URL
--token TEXT         Bearer token for authenticated API calls
--json              Output machine-readable JSON
--verbose           Print diagnostic details
--timeout FLOAT     HTTP timeout in seconds
```

### 7.3 Scan Options

```bash
--index TEXT         Index code. Repeatable. Example: CSI300
--type TEXT          Scan type: daily or weekly
--top-n INTEGER     Override scanner top-N selection
--direct            Run locally without API/ARQ
```

---

## 8. Functional Requirements

### FR-01 CLI Entrypoint

The project must expose a console command named `stockvalue`.

Example:

```bash
stockvalue --help
```

### FR-02 Scan Start Through API

The CLI must support queued scan start through the existing scanner API.

Acceptance criteria:

- User can pass one or more `--index` values.
- User can choose `daily` or `weekly`.
- User can optionally pass `--top-n`.
- CLI returns job id on success.
- CLI exits non-zero on API failure.

### FR-03 Direct Scan Execution

The CLI must support direct local execution by reusing existing scanner worker logic.

Acceptance criteria:

- Direct mode calls existing scanner code.
- Direct mode commits scanner results through existing repositories.
- Direct mode shows clear errors for missing DB/data configuration.
- Direct mode does not require Redis.

### FR-04 Scan Run Listing

The CLI must list scan runs with pagination and filters.

Acceptance criteria:

- User can filter by `status`.
- User can filter by `scan_type`.
- User can set `--limit`.
- Human output uses a readable table.
- JSON output is stable for automation.

### FR-05 Latest Scan View

The CLI must show the latest scan run for a given index code.

Acceptance criteria:

- User passes exactly one `--index`.
- CLI shows run id, status, counts, scan type, rules version, and timestamps.
- Missing scan history is reported clearly.

### FR-06 Candidate Listing

The CLI must list candidates for a run or latest index scan.

Acceptance criteria:

- User can pass `--run-id`.
- User can pass `--latest --index`.
- User can set `--limit`.
- Output includes ticker, index, composite score, safety margin, intrinsic value, risk level, and created time when available.

### FR-07 Candidate Detail

The CLI must show detailed information for a single candidate.

Acceptance criteria:

- User passes `candidate_id`.
- CLI includes scan provenance.
- CLI includes reasons and risk flags when present.
- CLI supports JSON output.

### FR-08 Watchlist Promotion

The CLI must add a candidate to the existing watchlist through backend integration.

Acceptance criteria:

- User passes `candidate_id`.
- CLI reports whether the ticker was newly added or already existed.
- CLI exits non-zero when the backend rejects the operation.

### FR-09 Authentication

The CLI must support authenticated API requests.

Acceptance criteria:

- Token can be supplied by `--token`.
- Token can be read from environment variable `STOCKVALUE_TOKEN`.
- API base URL can be supplied by `--api-url`.
- API base URL can be read from `STOCKVALUE_API_URL`.

### FR-10 Output Modes

The CLI must support human and JSON outputs.

Acceptance criteria:

- Default output is human-readable Rich tables.
- `--json` produces parseable JSON.
- JSON output should not include Rich formatting.

### FR-11 Exit Codes

The CLI must use predictable exit codes.

Acceptance criteria:

- `0`: command succeeded
- `1`: scan/API/backend operation failed
- `2`: invalid CLI usage, missing configuration, or invalid arguments

---

## 9. Non-Functional Requirements

### NFR-01 Reuse Existing Scanner Logic

CLI implementation must reuse existing scanner service, worker, repositories, and API endpoints. It must not duplicate valuation, screening, or scoring rules.

### NFR-02 Safe Operations

The CLI must avoid accidental high-cost scans by making index scope explicit. If no index is provided for a scan command, it may use configured defaults only when the command output clearly states the selected indexes.

### NFR-03 Observability

Verbose mode should show useful diagnostics:

- API URL used
- Request path
- Selected indexes
- Scan type
- Direct/API mode
- Error details from backend responses

Sensitive values such as tokens must never be printed.

### NFR-04 Automation Compatibility

JSON output must remain stable enough for scripts. Additive fields are allowed, but field renames should be avoided after V1.

### NFR-05 Local Development Compatibility

Direct mode must work without Redis/ARQ, assuming database and market data dependencies are available.

---

## 10. Suggested API Usage

V1 should use existing backend endpoints where possible:

| CLI Action | Backend/API or Code Path |
| --- | --- |
| Start queued scan | `POST /api/v1/scanner/runs` |
| List runs | `GET /api/v1/scanner/runs` |
| Latest run | `GET /api/v1/scanner/runs/latest/{index_code}` |
| List candidates | `GET /api/v1/scanner/runs/{run_id}/candidates` |
| Candidate detail | `GET /api/v1/scanner/candidates/{candidate_id}` |
| Add to watchlist | `POST /api/v1/scanner/candidates/{candidate_id}/watchlist` |
| Direct scan | `stockvaluefinder.market_scanner.worker.run_market_scan` |

---

## 11. Configuration

The CLI should support configuration in this precedence order:

1. Explicit CLI flags
2. Environment variables
3. Project defaults

Recommended environment variables:

```bash
STOCKVALUE_API_URL=http://localhost:8000
STOCKVALUE_TOKEN=<jwt-access-token>
```

Optional future variables:

```bash
STOCKVALUE_OUTPUT=json
STOCKVALUE_TIMEOUT=30
```

---

## 12. UX Requirements

### 12.1 Human Output

Human output should be compact and scannable.

Candidate table example:

```text
Ticker     Index   Score   Margin   Intrinsic   Risk     Created
600519.SH  CSI300  82.40   38.2%    1850.00     LOW      2026-06-05 17:30
```

### 12.2 Error Output

Errors must be actionable.

Good:

```text
Error: Worker is unavailable. Redis/ARQ is not connected; use --direct for local execution or start Redis.
```

Bad:

```text
Error: request failed
```

### 12.3 Sensitive Data

The CLI must never print bearer tokens, database URLs, passwords, or full authorization headers.

---

## 13. Milestones

### Milestone 1: Read-Only CLI

Deliver:

- `stockvalue scan runs`
- `stockvalue scan latest`
- `stockvalue scan candidates`
- `stockvalue scan candidate`
- Rich table output
- JSON output

Rationale:

This provides immediate visibility with low operational risk.

### Milestone 2: Queued Scan Start

Deliver:

- `stockvalue scan start`
- API auth support
- API base URL and token configuration
- Error handling for unavailable worker/Redis

### Milestone 3: Direct Local Execution

Deliver:

- `stockvalue scan run --direct`
- Direct use of existing scanner worker logic
- Local DB/data dependency validation

### Milestone 4: Watchlist Integration

Deliver:

- `stockvalue scan watchlist-add`
- Existing-watchlist detection
- Clear result output

---

## 14. Acceptance Criteria

V1 is accepted when:

- A user can start a queued daily scan for CSI300 from the terminal.
- A user can run a direct local scan without Redis.
- A user can view the latest scan status for CSI300.
- A user can list the top candidates from the latest scan.
- A user can inspect one candidate in detail.
- A user can add a candidate to the watchlist.
- All supported read commands have JSON output.
- CLI commands return documented exit codes.
- Unit tests cover command parsing and output formatting.
- Integration or mocked HTTP tests cover API client behavior.
- Direct mode tests verify that existing scanner worker logic is called rather than duplicated.

---

## 15. Risks and Mitigations

### Risk: CLI Duplicates Business Logic

Mitigation:

Keep scanner calculations in existing market scanner modules. CLI should only parse input, call APIs or existing worker functions, and format output.

### Risk: Confusing "Low Price" with Low Share Price

Mitigation:

Use terms such as margin of safety, intrinsic value, value score, and valuation level in CLI output. Avoid ranking by nominal share price.

### Risk: Local Direct Mode Has Hidden Dependencies

Mitigation:

Direct mode must validate database/data-provider configuration early and show a clear diagnostic before starting expensive work.

### Risk: Auth Friction

Mitigation:

Support `STOCKVALUE_TOKEN` and `STOCKVALUE_API_URL` environment variables so users do not need to repeat credentials on every command.

### Risk: Long-Running Scans Block Terminal

Mitigation:

Default production path should be queued `scan start`. Direct mode should be explicit with `--direct`.

---

## 16. Future Enhancements

- Saved CLI profiles for different environments
- `stockvalue scan export --format csv`
- `stockvalue scan explain <ticker>` for detailed reason breakdown
- Custom stock pool scan input from a file
- Progress polling for queued jobs
- Shell completion
- Config file support
- Direct login command that stores a local access token securely
- CI command that fails when no candidate meets threshold

