"""Unit tests for the market scanner Typer CLI."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

from stockvaluefinder.cli import app


runner = CliRunner()


class FakeClient:
    """Small async fake matching ScannerApiClient methods used by CLI tests."""

    last_init: dict[str, object | None] = {}
    calls: list[tuple[str, object]] = []
    fail: Exception | None = None

    def __init__(
        self,
        api_url: str,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.__class__.last_init = {
            "api_url": api_url,
            "token": token,
            "timeout": timeout,
        }

    @classmethod
    def reset(cls) -> None:
        cls.last_init = {}
        cls.calls = []
        cls.fail = None

    async def start_scan(
        self,
        index_codes: list[str],
        scan_type: str,
        top_n: int | None = None,
    ) -> dict[str, object]:
        if self.fail is not None:
            raise self.fail
        self.calls.append(("start_scan", (index_codes, scan_type, top_n)))
        return {"job_id": "job-1", "status": "queued"}

    async def list_runs(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        scan_type: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("list_runs", (page, limit, status, scan_type)))
        return {"runs": [], "pagination": {"total": 0, "page": page, "limit": limit}}

    async def latest_run(self, index_code: str) -> dict[str, object]:
        self.calls.append(("latest_run", index_code))
        return {
            "run_id": "run-1",
            "index_codes": [index_code],
            "scan_type": "daily",
            "status": "completed",
            "rules_version": "v1",
            "total_count": 300,
            "screened_count": 30,
            "candidate_count": 5,
            "started_at": "2026-06-05T10:00:00",
            "completed_at": "2026-06-05T10:05:00",
            "created_at": "2026-06-05T10:00:00",
        }

    async def list_candidates(
        self,
        run_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, object]:
        self.calls.append(("list_candidates", (run_id, page, limit)))
        return {
            "candidates": [
                {
                    "candidate_id": "candidate-1",
                    "run_id": run_id,
                    "ticker": "600519.SH",
                    "index_code": "CSI300",
                    "composite_score": 82.4,
                    "safety_margin": 0.382,
                    "intrinsic_value": 1850.0,
                    "risk_level": "LOW",
                    "created_at": "2026-06-05T10:00:00",
                }
            ],
            "pagination": {"total": 1, "page": page, "limit": limit},
        }

    async def candidate_detail(self, candidate_id: str) -> dict[str, object]:
        self.calls.append(("candidate_detail", candidate_id))
        return {"candidate_id": candidate_id, "ticker": "600519.SH"}

    async def add_to_watchlist(self, candidate_id: str) -> dict[str, object]:
        self.calls.append(("add_to_watchlist", candidate_id))
        return {"ticker": "600519.SH", "already_exists": False}


def test_root_help_displays_scan_commands() -> None:
    """Root command exposes the scan subcommand."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "scan" in result.output


def test_scan_start_requires_explicit_index(monkeypatch) -> None:
    """Queued scan start requires explicit --index values for safety."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(app, ["scan", "start"])

    assert result.exit_code == 2
    assert "At least one --index is required" in result.output
    assert FakeClient.calls == []


def test_scan_start_json_normalizes_indexes_and_calls_api(monkeypatch) -> None:
    """scan start --json prints parseable JSON and calls the API client."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(
        app,
        [
            "scan",
            "start",
            "--index",
            " csi300 ",
            "--index",
            "CSI300",
            "--type",
            "daily",
            "--top-n",
            "50",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"job_id": "job-1", "status": "queued"}
    assert FakeClient.calls == [("start_scan", (["CSI300"], "daily", 50))]


def test_scan_start_reads_api_config_from_environment(monkeypatch) -> None:
    """API URL, token, timeout, and JSON mode can come from environment."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setenv("STOCKVALUE_API_URL", "http://api.local")
    monkeypatch.setenv("STOCKVALUE_TOKEN", "env-token")
    monkeypatch.setenv("STOCKVALUE_TIMEOUT", "12.5")
    monkeypatch.setenv("STOCKVALUE_OUTPUT", "json")
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(app, ["scan", "start", "--index", "CSI300"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "queued"
    assert FakeClient.last_init == {
        "api_url": "http://api.local",
        "token": "env-token",
        "timeout": 12.5,
    }


def test_scan_candidates_requires_run_id_or_latest_index(monkeypatch) -> None:
    """candidates rejects missing source selection."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(app, ["scan", "candidates"])

    assert result.exit_code == 2
    assert "Either --run-id or --latest --index is required" in result.output


def test_scan_candidates_rejects_conflicting_run_id_and_latest(monkeypatch) -> None:
    """candidates rejects mutually exclusive --run-id and --latest."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(
        app,
        ["scan", "candidates", "--run-id", "run-1", "--latest", "--index", "CSI300"],
    )

    assert result.exit_code == 2
    assert "--run-id and --latest are mutually exclusive" in result.output


def test_scan_candidates_latest_fetches_latest_run_then_candidates(monkeypatch) -> None:
    """--latest --index resolves the latest run before listing candidates."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    FakeClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", FakeClient)

    result = runner.invoke(
        app,
        ["scan", "candidates", "--latest", "--index", "csi300", "--limit", "5"],
    )

    assert result.exit_code == 0, result.output
    assert FakeClient.calls == [
        ("latest_run", "CSI300"),
        ("list_candidates", ("run-1", 1, 5)),
    ]
    assert "600519.SH" in result.output


def test_scan_run_without_direct_exits_two() -> None:
    """scan run requires --direct in V1."""
    result = runner.invoke(app, ["scan", "run", "--index", "CSI300"])

    assert result.exit_code == 2
    assert "Use 'scan start' for queued execution" in result.output


def test_scan_run_direct_calls_worker(monkeypatch) -> None:
    """scan run --direct calls existing run_market_scan logic."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    calls: list[dict[str, object]] = []

    async def fake_run_market_scan(ctx, index_codes, scan_type, top_n):
        calls.append(
            {
                "ctx": ctx,
                "index_codes": index_codes,
                "scan_type": scan_type,
                "top_n": top_n,
            }
        )
        return {"status": "completed", "run_ids": ["run-1"]}

    monkeypatch.setattr(scanner_cli, "run_market_scan", fake_run_market_scan)

    result = runner.invoke(
        app,
        [
            "scan",
            "run",
            "--index",
            "csi300",
            "--type",
            "weekly",
            "--top-n",
            "10",
            "--direct",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "completed"
    assert calls == [
        {
            "ctx": {},
            "index_codes": ["CSI300"],
            "scan_type": "weekly",
            "top_n": 10,
        }
    ]


def test_watchlist_add_reports_already_exists(monkeypatch) -> None:
    """watchlist-add reports unchanged when API says ticker already exists."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    class ExistingClient(FakeClient):
        async def add_to_watchlist(self, candidate_id: str) -> dict[str, object]:
            self.calls.append(("add_to_watchlist", candidate_id))
            return {"ticker": "600519.SH", "already_exists": True}

    ExistingClient.reset()
    monkeypatch.setattr(scanner_cli, "ScannerApiClient", ExistingClient)

    result = runner.invoke(app, ["scan", "watchlist-add", "candidate-1"])

    assert result.exit_code == 0, result.output
    assert "Watchlist unchanged" in result.output
    assert "already_exists" in result.output


def test_sync_index_uses_live_provider_and_reports_count(monkeypatch) -> None:
    """sync-index fetches live constituents and upserts them."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    calls: dict[str, object] = {}

    async def fake_sync_index_constituents(index_code, use_dev_fallback=False):
        calls["index_code"] = index_code
        calls["use_dev_fallback"] = use_dev_fallback
        return SimpleNamespace(
            index_code=index_code,
            source="akshare",
            upserted_count=2,
            deactivated_count=0,
        )

    monkeypatch.setattr(
        scanner_cli,
        "sync_index_constituents",
        fake_sync_index_constituents,
    )

    result = runner.invoke(app, ["scan", "sync-index", "--index", "csi300"])

    assert result.exit_code == 0, result.output
    assert "Index constituents synced" in result.output
    assert "Upserted: 2" in result.output
    assert calls == {"index_code": "CSI300", "use_dev_fallback": False}


def test_sync_index_dev_fallback_is_explicit(monkeypatch) -> None:
    """sync-index passes explicit --dev-fallback into the sync helper."""
    import stockvaluefinder.tools.scanner_cli as scanner_cli

    calls: dict[str, object] = {}

    async def fake_sync_index_constituents(index_code, use_dev_fallback=False):
        calls["index_code"] = index_code
        calls["use_dev_fallback"] = use_dev_fallback
        return SimpleNamespace(
            index_code=index_code,
            source="dev-fallback",
            upserted_count=3,
            deactivated_count=0,
        )

    monkeypatch.setattr(
        scanner_cli,
        "sync_index_constituents",
        fake_sync_index_constituents,
    )

    result = runner.invoke(
        app,
        ["scan", "sync-index", "--index", "CSI300", "--dev-fallback", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == {
        "index_code": "CSI300",
        "source": "dev-fallback",
        "upserted_count": 3,
        "deactivated_count": 0,
    }
    assert calls == {"index_code": "CSI300", "use_dev_fallback": True}
