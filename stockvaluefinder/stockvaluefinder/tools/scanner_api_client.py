"""HTTP client for market scanner CLI operations."""

from __future__ import annotations

from typing import Any

import httpx


class ScannerCliError(Exception):
    """Base class for scanner CLI failures."""


class ScannerConfigError(ScannerCliError):
    """Raised when CLI configuration or arguments are invalid."""


class ScannerApiError(ScannerCliError):
    """Raised when the backend scanner API reports an operation failure."""


class ScannerAuthError(ScannerApiError):
    """Raised when authentication or authorization fails."""


class ScannerHttpError(ScannerApiError):
    """Raised when the backend returns a non-success HTTP response."""


class ScannerConnectionError(ScannerApiError):
    """Raised when the CLI cannot connect to the backend API."""


class ScannerApiClient:
    """Small async client around the existing scanner REST API."""

    def __init__(
        self,
        api_url: str,
        token: str | None = None,
        timeout: float = 30.0,
        transport: Any | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.transport = transport

    async def start_scan(
        self,
        index_codes: list[str],
        scan_type: str,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Start a queued scanner run through the backend API."""
        payload = {
            "index_codes": index_codes,
            "scan_type": scan_type,
            "top_n": top_n,
        }
        return await self._request("POST", "/api/v1/scanner/runs", json=payload)

    async def list_runs(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        scan_type: str | None = None,
    ) -> dict[str, Any]:
        """List scanner runs with optional filters."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            params["status"] = status
        if scan_type is not None:
            params["scan_type"] = scan_type
        return await self._request("GET", "/api/v1/scanner/runs", params=params)

    async def latest_run(self, index_code: str) -> dict[str, Any]:
        """Return the latest scanner run for one index code."""
        return await self._request("GET", f"/api/v1/scanner/runs/latest/{index_code}")

    async def list_candidates(
        self,
        run_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List candidates for a scanner run."""
        return await self._request(
            "GET",
            f"/api/v1/scanner/runs/{run_id}/candidates",
            params={"page": page, "limit": limit},
        )

    async def candidate_detail(self, candidate_id: str) -> dict[str, Any]:
        """Return full candidate detail."""
        return await self._request(
            "GET",
            f"/api/v1/scanner/candidates/{candidate_id}",
        )

    async def add_to_watchlist(self, candidate_id: str) -> dict[str, Any]:
        """Promote a scanner candidate into the watchlist."""
        return await self._request(
            "POST",
            f"/api/v1/scanner/candidates/{candidate_id}/watchlist",
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Execute one request and unwrap the ApiResponse data payload."""
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(
                base_url=self.api_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise ScannerConnectionError(str(exc)) from exc

        if response.status_code in (401, 403):
            raise ScannerAuthError(_extract_error_message(response))
        if not 200 <= response.status_code < 300:
            raise ScannerHttpError(_extract_error_message(response))

        try:
            payload = response.json()
        except ValueError as exc:
            raise ScannerHttpError("Backend returned non-JSON response.") from exc

        if not payload.get("success", False):
            raise ScannerApiError(str(payload.get("error") or "Scanner API failed."))
        data = payload.get("data")
        return data if isinstance(data, dict) else {"data": data}


def _extract_error_message(response: httpx.Response) -> str:
    """Extract a compact error message from an HTTP response."""
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    detail = payload.get("detail")
    error = payload.get("error")
    if isinstance(detail, str):
        return detail
    if isinstance(error, str):
        return error
    return f"HTTP {response.status_code}"
