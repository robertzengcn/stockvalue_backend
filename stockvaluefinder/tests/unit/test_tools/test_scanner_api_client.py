"""Unit tests for the market scanner HTTP API client."""

from __future__ import annotations

import json

import httpx
import pytest

from stockvaluefinder.tools.scanner_api_client import (
    ScannerApiClient,
    ScannerApiError,
    ScannerAuthError,
    ScannerConnectionError,
)


@pytest.mark.asyncio
async def test_start_scan_posts_payload_and_bearer_token() -> None:
    """start_scan posts to the scanner API with normalized URL and auth."""
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"success": True, "data": {"job_id": "job-1", "status": "queued"}},
        )

    client = ScannerApiClient(
        "http://backend.local/",
        token="secret-token",
        transport=httpx.MockTransport(handler),
    )

    data = await client.start_scan(["CSI300"], "daily", top_n=50)

    assert data == {"job_id": "job-1", "status": "queued"}
    assert seen["url"] == "http://backend.local/api/v1/scanner/runs"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["payload"] == {
        "index_codes": ["CSI300"],
        "scan_type": "daily",
        "top_n": 50,
    }


@pytest.mark.asyncio
async def test_list_runs_omits_auth_header_when_token_absent() -> None:
    """Requests do not send Authorization when no token is configured."""
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["query"] = str(request.url.query, "utf-8")
        return httpx.Response(
            200,
            json={"success": True, "data": {"runs": [], "pagination": {}}},
        )

    client = ScannerApiClient(
        "http://backend.local",
        transport=httpx.MockTransport(handler),
    )

    await client.list_runs(page=2, limit=10, status="completed", scan_type="weekly")

    assert seen["auth"] is None
    assert seen["query"] == "page=2&limit=10&status=completed&scan_type=weekly"


@pytest.mark.asyncio
async def test_api_success_false_raises_scanner_api_error() -> None:
    """ApiResponse success=false becomes ScannerApiError."""
    client = ScannerApiClient(
        "http://backend.local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"success": False, "error": "Worker not available."},
            )
        ),
    )

    with pytest.raises(ScannerApiError, match="Worker not available"):
        await client.latest_run("CSI300")


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_auth_status_raises_scanner_auth_error(status_code: int) -> None:
    """401 and 403 responses become ScannerAuthError."""
    client = ScannerApiClient(
        "http://backend.local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, json={"detail": "Forbidden"})
        ),
    )

    with pytest.raises(ScannerAuthError):
        await client.candidate_detail("candidate-1")


@pytest.mark.asyncio
async def test_connection_failure_raises_scanner_connection_error() -> None:
    """Network-level failures become ScannerConnectionError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = ScannerApiClient(
        "http://backend.local",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ScannerConnectionError, match="connection refused"):
        await client.add_to_watchlist("candidate-1")
