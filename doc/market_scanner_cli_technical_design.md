# Market Scanner CLI Technical Design

**Version**: V1.0  
**Date**: 2026-06-05  
**Related PRD**: `stockvalue_backend/doc/market_scanner_cli_prd.md`  
**Target Module**: StockValueFinder Backend  

---

## 1. Technical Goal

Add a first-class command line interface for market scanner operations. The CLI will let users start scans, run local direct scans, inspect scan runs, list candidates, view candidate details, and add candidates to the watchlist.

The CLI must reuse existing scanner behavior:

- API mode uses `stockvaluefinder/api/scanner_routes.py`.
- Direct mode uses `stockvaluefinder/market_scanner/worker.py::run_market_scan`.
- Output formatting is CLI-only and must not introduce new valuation or screening logic.

---

## 2. Existing Reuse Points

### 2.1 Scanner API

Existing API prefix:

```text
/api/v1/scanner
```

Existing endpoints to reuse:

| CLI Operation | Endpoint |
| --- | --- |
| Start queued scan | `POST /api/v1/scanner/runs` |
| List scan runs | `GET /api/v1/scanner/runs` |
| Latest scan | `GET /api/v1/scanner/runs/latest/{index_code}` |
| List candidates | `GET /api/v1/scanner/runs/{run_id}/candidates` |
| Candidate detail | `GET /api/v1/scanner/candidates/{candidate_id}` |
| Add to watchlist | `POST /api/v1/scanner/candidates/{candidate_id}/watchlist` |

### 2.2 Scanner Worker

Direct local execution should call:

```python
from stockvaluefinder.market_scanner.worker import run_market_scan
```

Direct mode should pass:

```python
await run_market_scan(
    {},
    index_codes=[...],
    scan_type="daily" | "weekly",
    top_n=...,
)
```

This preserves:

- Existing `ScanType` validation
- Existing top-N override behavior
- Existing database persistence
- Existing concurrent scan prevention
- Existing per-index orchestration

### 2.3 Existing CLI Pattern

The project already uses Typer and Rich in:

```text
stockvaluefinder/tools/reconcile.py
```

The scanner CLI should follow the same patterns:

- `typer.Typer`
- `rich.console.Console`
- `rich.table.Table`
- JSON output option
- Explicit `typer.Exit(code=...)`

---

## 3. Proposed File Structure

```text
stockvaluefinder/
├── cli.py
└── tools/
    ├── scanner_api_client.py
    ├── scanner_cli.py
    └── scanner_formatters.py

tests/
└── unit/
    └── test_tools/
        ├── test_scanner_api_client.py
        ├── test_scanner_cli.py
        └── test_scanner_formatters.py
```

### 3.1 `stockvaluefinder/cli.py`

Top-level Typer application.

Responsibilities:

- Create the root `stockvalue` CLI app.
- Register scanner subcommands under `scan`.
- Provide global help.

Suggested shape:

```python
import typer

from stockvaluefinder.tools.scanner_cli import app as scanner_app

app = typer.Typer(name="stockvalue", help="StockValueFinder command line tools.")
app.add_typer(scanner_app, name="scan", help="Market scanner operations.")

if __name__ == "__main__":
    app()
```

### 3.2 `stockvaluefinder/tools/scanner_cli.py`

Typer command definitions.

Responsibilities:

- Parse command options.
- Resolve runtime configuration.
- Call API client or direct worker function.
- Render human or JSON output.
- Convert known failures into documented exit codes.

Commands:

```text
start
run
runs
latest
candidates
candidate
watchlist-add
```

### 3.3 `stockvaluefinder/tools/scanner_api_client.py`

Small HTTP client around scanner API endpoints.

Responsibilities:

- Manage API base URL normalization.
- Add bearer token header when present.
- Make requests with timeout.
- Parse `ApiResponse` wrapper.
- Raise typed errors for HTTP, API, auth, and connection failures.

This module should use `httpx`, which is already a project dependency.

### 3.4 `stockvaluefinder/tools/scanner_formatters.py`

Formatting helpers.

Responsibilities:

- Build Rich tables for scan runs.
- Build Rich tables for candidates.
- Build detail panels or plain sections for candidate details.
- Serialize raw response payloads to JSON.

Keep all Rich-specific logic here so command functions stay small.

---

## 4. Packaging

Add a console script to `stockvaluefinder/pyproject.toml`:

```toml
[project.scripts]
stockvalue = "stockvaluefinder.cli:app"
```

Development usage after installation:

```bash
uv run stockvalue --help
```

Fallback usage without script installation:

```bash
uv run python -m stockvaluefinder.cli --help
```

---

## 5. Runtime Configuration

### 5.1 Configuration Sources

Apply this precedence:

1. CLI option
2. Environment variable
3. Default

Recommended defaults:

| Setting | CLI Option | Environment Variable | Default |
| --- | --- | --- | --- |
| API URL | `--api-url` | `STOCKVALUE_API_URL` | `http://localhost:8000` |
| Token | `--token` | `STOCKVALUE_TOKEN` | `None` |
| Timeout | `--timeout` | `STOCKVALUE_TIMEOUT` | `30.0` |
| Output JSON | `--json` | `STOCKVALUE_OUTPUT=json` | `False` |

### 5.2 Runtime Config Model

Use a small dataclass, not Pydantic, because this is CLI-local configuration.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ScannerCliConfig:
    api_url: str
    token: str | None
    timeout: float
    json_output: bool
    verbose: bool
```

Validation:

- `api_url` must not be empty.
- `timeout` must be greater than zero.
- Token should be accepted as opaque string and never printed.

---

## 6. API Client Design

### 6.1 Class Interface

```python
class ScannerApiClient:
    def __init__(
        self,
        api_url: str,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None: ...

    async def start_scan(
        self,
        index_codes: list[str],
        scan_type: str,
        top_n: int | None = None,
    ) -> dict: ...

    async def list_runs(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        scan_type: str | None = None,
    ) -> dict: ...

    async def latest_run(self, index_code: str) -> dict: ...

    async def list_candidates(
        self,
        run_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict: ...

    async def candidate_detail(self, candidate_id: str) -> dict: ...

    async def add_to_watchlist(self, candidate_id: str) -> dict: ...
```

### 6.2 Response Handling

The API uses an `ApiResponse` wrapper:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

Client behavior:

- If HTTP status is `401` or `403`, raise `ScannerAuthError`.
- If HTTP status is not 2xx, raise `ScannerHttpError`.
- If response JSON has `success=false`, raise `ScannerApiError`.
- Otherwise return `data`.

### 6.3 Error Types

```python
class ScannerCliError(Exception): ...
class ScannerConfigError(ScannerCliError): ...
class ScannerApiError(ScannerCliError): ...
class ScannerAuthError(ScannerApiError): ...
class ScannerHttpError(ScannerApiError): ...
class ScannerConnectionError(ScannerApiError): ...
```

Exit code mapping:

| Error | Exit Code |
| --- | --- |
| Success | `0` |
| `ScannerApiError` | `1` |
| `ScannerConnectionError` | `1` |
| Direct scan returns `status=failed` | `1` |
| `ScannerConfigError` | `2` |
| Typer usage errors | `2` |

---

## 7. Command Behavior

### 7.1 `stockvalue scan start`

Queued scan through API/ARQ.

Options:

```text
--index TEXT      Repeatable. Defaults to scanner API request default only if omitted.
--type TEXT       daily | weekly. Default: daily.
--top-n INTEGER   Optional.
--api-url TEXT
--token TEXT
--json
--verbose
--timeout FLOAT
```

Validation:

- `--type` must be `daily` or `weekly`.
- `--top-n`, when provided, must be greater than zero.

Request:

```json
{
  "index_codes": ["CSI300", "CSI500"],
  "scan_type": "daily",
  "top_n": 50
}
```

Human output:

```text
Scan queued
Job ID: abc123
Status: queued
```

JSON output:

```json
{
  "job_id": "abc123",
  "status": "queued"
}
```

### 7.2 `stockvalue scan run`

Direct local scan.

Options:

```text
--index TEXT      Repeatable.
--type TEXT       daily | weekly. Default: daily.
--top-n INTEGER   Optional.
--direct          Required for V1 direct execution.
--json
--verbose
```

V1 rule:

- If `--direct` is omitted, print a clear error telling the user to use `scan start` for queued execution or add `--direct` for local execution.

Direct implementation:

```python
result = await run_market_scan(
    {},
    index_codes=list(indexes) or None,
    scan_type=scan_type,
    top_n=top_n,
)
```

Human output:

```text
Direct scan completed
Status: completed
Indexes: CSI300
Type: weekly
```

Failure output:

```text
Direct scan failed
Error: <sanitized error message>
```

### 7.3 `stockvalue scan runs`

List historical scan runs.

Options:

```text
--page INTEGER
--limit INTEGER
--status TEXT
--type TEXT
--api-url TEXT
--token TEXT
--json
```

Human columns:

```text
Run ID | Indexes | Type | Status | Total | Screened | Candidates | Started | Completed
```

### 7.4 `stockvalue scan latest`

Show latest run for one index.

Options:

```text
--index TEXT      Required.
--api-url TEXT
--token TEXT
--json
```

Validation:

- Exactly one index is required.

### 7.5 `stockvalue scan candidates`

List candidates from a run.

Options:

```text
--run-id UUID
--latest
--index TEXT
--page INTEGER
--limit INTEGER
--api-url TEXT
--token TEXT
--json
```

Validation:

- Either `--run-id` or `--latest --index` is required.
- `--run-id` and `--latest` are mutually exclusive.

When `--latest --index` is used:

1. Call latest run endpoint.
2. Extract `run_id`.
3. Call candidate list endpoint.

Human columns:

```text
Ticker | Index | Score | Safety Margin | Intrinsic Value | Risk | Created
```

### 7.6 `stockvalue scan candidate`

Show candidate detail.

Argument:

```text
candidate_id
```

Human output sections:

- Identity: candidate id, ticker, index, run id
- Score: composite score, safety margin, intrinsic value, risk level
- Reasons: selected reasons when present
- Risk flags: risk flags when present
- Provenance: scan created time and rules version when available

### 7.7 `stockvalue scan watchlist-add`

Add a candidate to the watchlist.

Argument:

```text
candidate_id
```

Human output:

```text
Watchlist updated
Ticker: 600519.SH
Status: added
```

If already present:

```text
Watchlist unchanged
Ticker: 600519.SH
Status: already_exists
```

---

## 8. Output Formatting

### 8.1 JSON Output

Use `json.dumps(payload, indent=2, default=str)`.

Rules:

- Return the API `data` payload, not the full HTTP response.
- For direct mode, return the result dict from `run_market_scan` plus command context fields.
- Do not include Rich markup.

### 8.2 Human Output

Use Rich tables for lists and compact key/value sections for details.

Candidate list table:

```text
Ticker     Index   Score   Margin   Intrinsic   Risk     Created
600519.SH  CSI300  82.40   38.2%    1850.00     LOW      2026-06-05 17:30
```

Formatting helpers should tolerate missing optional fields and display `-` instead of raising errors.

### 8.3 Verbose Output

Verbose mode may print:

- API URL
- Endpoint path
- HTTP method
- Scan type
- Index codes
- Direct/API mode

Verbose mode must not print:

- Bearer token
- Full authorization header
- Database URL
- Passwords

---

## 9. Authentication and Security

### 9.1 Token Handling

Token sources:

1. `--token`
2. `STOCKVALUE_TOKEN`

Request header:

```text
Authorization: Bearer <token>
```

Never print the token. For verbose mode, use:

```text
Token: provided
```

or:

```text
Token: not provided
```

### 9.2 Admin-Only Commands

The backend currently controls authorization. The CLI should not attempt to locally infer role.

Commands likely requiring admin token:

- `scan start`

Commands requiring authenticated token:

- `scan runs`
- `scan latest`
- `scan candidates`
- `scan candidate`
- `scan watchlist-add`

If backend returns `403`, CLI should report:

```text
Error: Forbidden. Your token does not have permission for this operation.
```

---

## 10. Direct Mode Technical Notes

### 10.1 Dependency Requirements

Direct mode requires:

- Database URL and migrations available
- Market data provider dependencies available
- Valid configuration for data services

Direct mode does not require:

- FastAPI server
- Redis
- ARQ worker

### 10.2 Session and Commit Behavior

Do not open a separate session in the CLI. `run_market_scan` already opens `async_session_maker()` and commits after each index scan. Calling it directly avoids duplicating transaction behavior.

### 10.3 Error Handling

If `run_market_scan` returns:

```python
{"status": "failed", "error": "..."}
```

CLI exits with code `1`.

If it raises unexpectedly, catch the exception, sanitize the message, and exit with code `1`.

---

## 11. Input Validation

### 11.1 Scan Type

Allowed values:

```text
daily
weekly
```

Use `typing.Literal["daily", "weekly"]` or a Typer enum to keep command help clear.

### 11.2 Index Codes

V1 should accept free-form index strings to avoid hardcoding future index pools. It should normalize by:

- Stripping whitespace
- Uppercasing
- Removing duplicates while preserving order

Validation:

- Empty string is invalid.
- If omitted for `scan start`, send API default or use `["CSI300", "CSI500"]`.
- If omitted for direct mode, pass `None` to `run_market_scan` so existing scanner config defaults apply.

### 11.3 Pagination

Validation:

- `page >= 1`
- `1 <= limit <= 100`

This matches existing API behavior and prevents accidental oversized requests.

---

## 12. Testing Strategy

### 12.1 Unit Tests: API Client

File:

```text
tests/unit/test_tools/test_scanner_api_client.py
```

Cases:

- Builds correct URL for each endpoint.
- Sends bearer token when configured.
- Omits auth header when token is absent.
- Converts `success=false` to `ScannerApiError`.
- Converts `401` and `403` to `ScannerAuthError`.
- Converts connection failures to `ScannerConnectionError`.
- Normalizes trailing slash in API URL.

Use `httpx.MockTransport` to avoid real network calls.

### 12.2 Unit Tests: CLI Commands

File:

```text
tests/unit/test_tools/test_scanner_cli.py
```

Cases:

- `--help` displays scan commands.
- `scan start` validates scan type and top-N.
- `scan start --json` prints parseable JSON.
- `scan candidates` rejects missing `--run-id` or `--latest --index`.
- `scan candidates` rejects conflicting `--run-id` and `--latest`.
- `scan run` without `--direct` exits with code `2`.
- `scan run --direct` calls `run_market_scan`.
- API failures exit with code `1`.
- Config failures exit with code `2`.

Use Typer `CliRunner`.

### 12.3 Unit Tests: Formatters

File:

```text
tests/unit/test_tools/test_scanner_formatters.py
```

Cases:

- Run table renders expected columns.
- Candidate table renders expected columns.
- Missing optional fields render as `-`.
- JSON output serializes UUID and datetime values with `default=str`.

### 12.4 Minimal Integration Test

Optional V1 integration test:

```text
tests/integration/test_scanner_cli_api.py
```

This can use FastAPI test app or mocked HTTP server if full auth setup is too heavy.

---

## 13. Implementation Plan

### Step 1: Add CLI Entrypoint

Files:

- `stockvaluefinder/stockvaluefinder/cli.py`
- `stockvaluefinder/pyproject.toml`

Tasks:

- Create root Typer app.
- Add `[project.scripts]`.
- Verify `uv run stockvalue --help`.

### Step 2: Add API Client

Files:

- `stockvaluefinder/stockvaluefinder/tools/scanner_api_client.py`
- `stockvaluefinder/tests/unit/test_tools/test_scanner_api_client.py`

Tasks:

- Implement typed errors.
- Implement endpoint methods.
- Add MockTransport tests.

### Step 3: Add Formatters

Files:

- `stockvaluefinder/stockvaluefinder/tools/scanner_formatters.py`
- `stockvaluefinder/tests/unit/test_tools/test_scanner_formatters.py`

Tasks:

- Implement table builders.
- Implement JSON serialization helper.

### Step 4: Add Read-Only Commands

Files:

- `stockvaluefinder/stockvaluefinder/tools/scanner_cli.py`
- `stockvaluefinder/tests/unit/test_tools/test_scanner_cli.py`

Tasks:

- Implement `runs`, `latest`, `candidates`, `candidate`.
- Wire config resolution and output modes.

### Step 5: Add Write Commands

Tasks:

- Implement `start`.
- Implement `watchlist-add`.
- Validate auth/API error mapping.

### Step 6: Add Direct Mode

Tasks:

- Implement `run --direct`.
- Call `run_market_scan`.
- Validate failure exit code.

### Step 7: Documentation Update

Files:

- `doc/LOCAL_DEVELOPMENT.md`
- `doc/API_REFERENCE.md` or CLI-specific usage doc

Tasks:

- Add CLI install/run examples.
- Add environment variable examples.

---

## 14. Verification Commands

Run from:

```text
stockvalue_backend/stockvaluefinder
```

Suggested checks:

```bash
uv run ruff check stockvaluefinder tests/unit/test_tools
uv run mypy stockvaluefinder
uv run pytest tests/unit/test_tools/test_scanner_api_client.py -q
uv run pytest tests/unit/test_tools/test_scanner_formatters.py -q
uv run pytest tests/unit/test_tools/test_scanner_cli.py -q
uv run stockvalue --help
uv run stockvalue scan --help
```

Manual checks with backend running:

```bash
export STOCKVALUE_API_URL=http://localhost:8000
export STOCKVALUE_TOKEN=<jwt-access-token>

uv run stockvalue scan latest --index CSI300
uv run stockvalue scan candidates --latest --index CSI300 --limit 20
uv run stockvalue scan start --index CSI300 --type daily --top-n 50
```

Direct local check:

```bash
uv run stockvalue scan run --index CSI300 --type daily --top-n 10 --direct
```

---

## 15. Open Questions

1. Should the CLI default `scan start` indexes to `["CSI300", "CSI500"]`, or should it require explicit `--index` values for safety?
2. Should `scan candidates --latest --index CSI300` list candidates only from the latest completed run, or the latest run regardless of status?
3. Should `watchlist-add` be available through direct DB mode in the future, or remain API-only?
4. Should the CLI support token acquisition through `stockvalue auth login` in a later version?
5. Should candidate export to CSV be part of V1 or deferred?

