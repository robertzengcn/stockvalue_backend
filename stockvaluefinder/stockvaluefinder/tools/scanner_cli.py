"""Typer CLI commands for market scanner operations."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Annotated, Any

import typer
from rich.console import Console

from stockvaluefinder.tools.scanner_api_client import (
    ScannerApiClient,
    ScannerApiError,
    ScannerConfigError,
)
from stockvaluefinder.tools.scanner_formatters import (
    build_candidate_detail,
    build_candidate_table,
    build_run_table,
    format_json,
)

app = typer.Typer(name="scan", help="Market scanner operations.")
console = Console()
err_console = Console(stderr=True)


@dataclass(frozen=True)
class ScannerCliConfig:
    """Resolved scanner CLI runtime configuration."""

    api_url: str
    token: str | None
    timeout: float
    json_output: bool
    verbose: bool


async def run_market_scan(
    ctx: dict[str, Any],
    index_codes: list[str] | None = None,
    scan_type: str = "daily",
    top_n: int | None = None,
) -> dict[str, str]:
    """Lazy wrapper around the existing direct scanner worker function."""
    from stockvaluefinder.market_scanner.worker import run_market_scan as worker_run

    return await worker_run(
        ctx, index_codes=index_codes, scan_type=scan_type, top_n=top_n
    )


async def sync_index_constituents(
    index_code: str,
    use_dev_fallback: bool = False,
):
    """Lazy wrapper around index constituent sync to keep CLI help DB-free."""
    from stockvaluefinder.tools.index_sync import (
        sync_index_constituents as sync_index_constituents_impl,
    )

    return await sync_index_constituents_impl(
        index_code,
        use_dev_fallback=use_dev_fallback,
    )


@app.command()
def start(
    index: Annotated[
        list[str] | None,
        typer.Option("--index", help="Index code. Repeat for multiple indexes."),
    ] = None,
    scan_type: Annotated[str, typer.Option("--type", help="daily or weekly")] = "daily",
    top_n: Annotated[
        int | None, typer.Option("--top-n", help="Override scanner top-N.")
    ] = None,
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """Start a queued scanner run through the backend API."""
    _run_command(
        _start_async(
            index, scan_type, top_n, api_url, token, json_output, verbose, timeout
        )
    )


@app.command()
def run(
    index: Annotated[
        list[str] | None,
        typer.Option("--index", help="Index code. Repeat for multiple indexes."),
    ] = None,
    scan_type: Annotated[str, typer.Option("--type", help="daily or weekly")] = "daily",
    top_n: Annotated[
        int | None, typer.Option("--top-n", help="Override scanner top-N.")
    ] = None,
    direct: Annotated[
        bool, typer.Option("--direct", help="Run locally without API/ARQ.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
) -> None:
    """Run a local direct scanner execution."""
    _run_command(
        _run_direct_async(index, scan_type, top_n, direct, json_output, verbose)
    )


@app.command()
def runs(
    page: Annotated[int, typer.Option("--page", help="Page number.")] = 1,
    limit: Annotated[int, typer.Option("--limit", help="Items per page.")] = 20,
    status: Annotated[
        str | None, typer.Option("--status", help="Run status filter.")
    ] = None,
    scan_type: Annotated[
        str | None, typer.Option("--type", help="daily or weekly")
    ] = None,
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """List recent scan runs."""
    _run_command(
        _runs_async(
            page,
            limit,
            status,
            scan_type,
            api_url,
            token,
            json_output,
            verbose,
            timeout,
        )
    )


@app.command()
def latest(
    index: Annotated[str, typer.Option("--index", help="Index code, e.g. CSI300.")],
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """Show the latest scan run for one index."""
    _run_command(_latest_async(index, api_url, token, json_output, verbose, timeout))


@app.command()
def candidates(
    run_id: Annotated[str | None, typer.Option("--run-id", help="Scan run id.")] = None,
    latest: Annotated[
        bool, typer.Option("--latest", help="Use latest run for --index.")
    ] = False,
    index: Annotated[
        str | None, typer.Option("--index", help="Index code for --latest.")
    ] = None,
    page: Annotated[int, typer.Option("--page", help="Page number.")] = 1,
    limit: Annotated[int, typer.Option("--limit", help="Items per page.")] = 20,
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """List scan candidates by run or latest index scan."""
    _run_command(
        _candidates_async(
            run_id,
            latest,
            index,
            page,
            limit,
            api_url,
            token,
            json_output,
            verbose,
            timeout,
        )
    )


@app.command()
def candidate(
    candidate_id: Annotated[str, typer.Argument(help="Candidate id.")],
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """Show one scan candidate in detail."""
    _run_command(
        _candidate_async(candidate_id, api_url, token, json_output, verbose, timeout)
    )


@app.command("watchlist-add")
def watchlist_add(
    candidate_id: Annotated[str, typer.Argument(help="Candidate id.")],
    api_url: Annotated[
        str | None, typer.Option("--api-url", help="Backend API base URL.")
    ] = None,
    token: Annotated[str | None, typer.Option("--token", help="Bearer token.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Print diagnostics.")
    ] = False,
    timeout: Annotated[
        float | None, typer.Option("--timeout", help="HTTP timeout seconds.")
    ] = None,
) -> None:
    """Add one scan candidate to the watchlist."""
    _run_command(
        _watchlist_add_async(
            candidate_id, api_url, token, json_output, verbose, timeout
        )
    )


@app.command("sync-index")
def sync_index(
    index: Annotated[str, typer.Option("--index", help="Index code, e.g. CSI300.")],
    dev_fallback: Annotated[
        bool,
        typer.Option(
            "--dev-fallback",
            help="Use small DEVELOPMENT_MODE-only fallback constituents.",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON.")] = False,
) -> None:
    """Sync index constituents for scanner runs."""
    _run_command(_sync_index_async(index, dev_fallback, json_output))


async def _start_async(
    index: list[str] | None,
    scan_type: str,
    top_n: int | None,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    _validate_scan_type(scan_type)
    _validate_top_n(top_n)
    indexes = _normalize_indexes(index)
    if not indexes:
        raise ScannerConfigError("At least one --index is required for scan start.")
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    _print_verbose(config, "POST /api/v1/scanner/runs", indexes, scan_type)
    data = await _client(config).start_scan(indexes, scan_type, top_n)
    if config.json_output:
        console.print(format_json(data))
    else:
        console.print("[bold green]Scan queued[/bold green]")
        console.print(f"Job ID: {data.get('job_id', '-')}")
        console.print(f"Status: {data.get('status', '-')}")


async def _run_direct_async(
    index: list[str] | None,
    scan_type: str,
    top_n: int | None,
    direct: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    _validate_scan_type(scan_type)
    _validate_top_n(top_n)
    if not direct:
        raise ScannerConfigError(
            "Use 'scan start' for queued execution or add --direct for local execution."
        )
    indexes = _normalize_indexes(index)
    if verbose and not json_output:
        console.print(
            f"Mode: direct | Type: {scan_type} | Indexes: {indexes or 'scanner defaults'}"
        )
    try:
        result = await run_market_scan(
            {},
            index_codes=indexes or None,
            scan_type=scan_type,
            top_n=top_n,
        )
    except Exception as exc:  # noqa: BLE001
        raise ScannerApiError(f"Direct scan failed: {_sanitize(str(exc))}") from exc
    payload = {
        **result,
        "mode": "direct",
        "index_codes": indexes or None,
        "scan_type": scan_type,
    }
    if result.get("status") == "failed":
        if json_output:
            console.print(format_json(payload))
        raise ScannerApiError(_sanitize(result.get("error", "Direct scan failed.")))
    if json_output:
        console.print(format_json(payload))
    else:
        console.print("[bold green]Direct scan completed[/bold green]")
        console.print(f"Status: {result.get('status', '-')}")
        console.print(
            f"Indexes: {','.join(indexes) if indexes else 'scanner defaults'}"
        )
        console.print(f"Type: {scan_type}")


async def _runs_async(
    page: int,
    limit: int,
    status: str | None,
    scan_type: str | None,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    _validate_pagination(page, limit)
    if scan_type is not None:
        _validate_scan_type(scan_type)
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    _print_verbose(config, "GET /api/v1/scanner/runs")
    data = await _client(config).list_runs(page, limit, status, scan_type)
    console.print(
        format_json(data)
        if config.json_output
        else build_run_table(data.get("runs", []))
    )


async def _latest_async(
    index: str,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    indexes = _normalize_indexes([index])
    if len(indexes) != 1:
        raise ScannerConfigError("Exactly one --index is required.")
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    _print_verbose(config, f"GET /api/v1/scanner/runs/latest/{indexes[0]}", indexes)
    data = await _client(config).latest_run(indexes[0])
    console.print(format_json(data) if config.json_output else build_run_table([data]))


async def _candidates_async(
    run_id: str | None,
    latest: bool,
    index: str | None,
    page: int,
    limit: int,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    _validate_pagination(page, limit)
    if run_id and latest:
        raise ScannerConfigError("--run-id and --latest are mutually exclusive.")
    if not run_id and not (latest and index):
        raise ScannerConfigError("Either --run-id or --latest --index is required.")
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    client = _client(config)
    resolved_run_id = run_id
    if latest:
        indexes = _normalize_indexes([index or ""])
        if len(indexes) != 1:
            raise ScannerConfigError("Exactly one --index is required with --latest.")
        _print_verbose(config, f"GET /api/v1/scanner/runs/latest/{indexes[0]}", indexes)
        latest_run = await client.latest_run(indexes[0])
        resolved_run_id = str(latest_run.get("run_id", ""))
    if not resolved_run_id:
        raise ScannerConfigError("Could not resolve scan run id.")
    _print_verbose(config, f"GET /api/v1/scanner/runs/{resolved_run_id}/candidates")
    data = await client.list_candidates(resolved_run_id, page, limit)
    console.print(
        format_json(data)
        if config.json_output
        else build_candidate_table(data.get("candidates", []))
    )


async def _candidate_async(
    candidate_id: str,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    _print_verbose(config, f"GET /api/v1/scanner/candidates/{candidate_id}")
    data = await _client(config).candidate_detail(candidate_id)
    console.print(
        format_json(data) if config.json_output else build_candidate_detail(data)
    )


async def _watchlist_add_async(
    candidate_id: str,
    api_url: str | None,
    token: str | None,
    json_output: bool,
    verbose: bool,
    timeout: float | None,
) -> None:
    config = _resolve_config(api_url, token, timeout, json_output, verbose)
    _print_verbose(config, f"POST /api/v1/scanner/candidates/{candidate_id}/watchlist")
    data = await _client(config).add_to_watchlist(candidate_id)
    if config.json_output:
        console.print(format_json(data))
        return
    unchanged = bool(data.get("already_exists"))
    console.print(
        "[bold yellow]Watchlist unchanged[/bold yellow]"
        if unchanged
        else "[bold green]Watchlist updated[/bold green]"
    )
    console.print(f"Ticker: {data.get('ticker', '-')}")
    console.print(f"Status: {'already_exists' if unchanged else 'added'}")


async def _sync_index_async(
    index: str,
    dev_fallback: bool,
    json_output: bool,
) -> None:
    indexes = _normalize_indexes([index])
    if len(indexes) != 1:
        raise ScannerConfigError("Exactly one --index is required.")
    try:
        result = await sync_index_constituents(
            indexes[0],
            use_dev_fallback=dev_fallback,
        )
    except ValueError as exc:
        raise ScannerConfigError(str(exc)) from exc
    payload = {
        "index_code": result.index_code,
        "source": result.source,
        "upserted_count": result.upserted_count,
        "deactivated_count": result.deactivated_count,
    }
    if json_output:
        console.print(format_json(payload))
        return
    console.print("[bold green]Index constituents synced[/bold green]")
    console.print(f"Index: {result.index_code}")
    console.print(f"Source: {result.source}")
    console.print(f"Upserted: {result.upserted_count}")
    console.print(f"Deactivated: {result.deactivated_count}")


def _run_command(coro: Any) -> None:
    try:
        asyncio.run(coro)
    except ScannerConfigError as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from None
    except ScannerApiError as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from None


def _client(config: ScannerCliConfig) -> ScannerApiClient:
    return ScannerApiClient(config.api_url, token=config.token, timeout=config.timeout)


def _resolve_config(
    api_url: str | None,
    token: str | None,
    timeout: float | None,
    json_output: bool,
    verbose: bool,
) -> ScannerCliConfig:
    resolved_api_url = (
        api_url or os.getenv("STOCKVALUE_API_URL") or "http://localhost:8000"
    )
    resolved_token = token or os.getenv("STOCKVALUE_TOKEN")
    try:
        resolved_timeout = (
            timeout
            if timeout is not None
            else float(os.getenv("STOCKVALUE_TIMEOUT", "30.0"))
        )
    except (TypeError, ValueError) as exc:
        raise ScannerConfigError(
            "STOCKVALUE_TIMEOUT/--timeout must be a number."
        ) from exc
    resolved_json = json_output or os.getenv("STOCKVALUE_OUTPUT", "").lower() == "json"
    if not resolved_api_url.strip():
        raise ScannerConfigError("API URL must not be empty.")
    if resolved_timeout <= 0:
        raise ScannerConfigError("--timeout must be greater than zero.")
    return ScannerCliConfig(
        api_url=resolved_api_url,
        token=resolved_token,
        timeout=resolved_timeout,
        json_output=resolved_json,
        verbose=verbose,
    )


def _normalize_indexes(indexes: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in indexes or []:
        code = raw.strip().upper()
        if not code:
            raise ScannerConfigError("--index must not be empty.")
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized


def _validate_scan_type(scan_type: str) -> None:
    if scan_type not in {"daily", "weekly"}:
        raise ScannerConfigError("--type must be 'daily' or 'weekly'.")


def _validate_top_n(top_n: int | None) -> None:
    if top_n is not None and top_n <= 0:
        raise ScannerConfigError("--top-n must be greater than zero.")


def _validate_pagination(page: int, limit: int) -> None:
    if page < 1:
        raise ScannerConfigError("--page must be greater than or equal to 1.")
    if limit < 1 or limit > 100:
        raise ScannerConfigError("--limit must be between 1 and 100.")


def _print_verbose(
    config: ScannerCliConfig,
    request_path: str,
    indexes: list[str] | None = None,
    scan_type: str | None = None,
) -> None:
    if not config.verbose or config.json_output:
        return
    console.print(f"API URL: {config.api_url}")
    console.print(f"Request: {request_path}")
    console.print(f"Token: {'provided' if config.token else 'not provided'}")
    if indexes is not None:
        console.print(f"Indexes: {','.join(indexes)}")
    if scan_type is not None:
        console.print(f"Type: {scan_type}")


def _sanitize(message: str) -> str:
    redacted = message
    for secret in (os.getenv("DATABASE_URL"), os.getenv("STOCKVALUE_TOKEN")):
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted
