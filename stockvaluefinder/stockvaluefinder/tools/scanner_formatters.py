"""Rich and JSON formatting helpers for scanner CLI output."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def format_json(payload: Any) -> str:
    """Serialize a CLI payload as stable, machine-readable JSON."""
    return json.dumps(payload, indent=2, default=str)


def build_run_table(runs: list[dict[str, Any]]) -> Table:
    """Build a Rich table for scan run summaries."""
    table = Table(
        title="Market Scan Runs", show_header=True, header_style="bold magenta"
    )
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Indexes")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Total", justify="right")
    table.add_column("Screened", justify="right")
    table.add_column("Candidates", justify="right")
    table.add_column("Started")
    table.add_column("Completed")

    for run in runs:
        table.add_row(
            _short(run.get("run_id")),
            _format_indexes(run.get("index_codes")),
            _dash(run.get("scan_type")),
            _dash(run.get("status")),
            _dash(run.get("total_count")),
            _dash(run.get("screened_count")),
            _dash(run.get("candidate_count")),
            _format_datetime(run.get("started_at")),
            _format_datetime(run.get("completed_at")),
        )
    return table


def build_candidate_table(candidates: list[dict[str, Any]]) -> Table:
    """Build a Rich table for candidate summaries."""
    table = Table(
        title="Market Scan Candidates", show_header=True, header_style="bold magenta"
    )
    table.add_column("Candidate ID", style="cyan", no_wrap=True)
    table.add_column("Ticker", no_wrap=True)
    table.add_column("Index")
    table.add_column("Score", justify="right")
    table.add_column("Safety Margin", justify="right")
    table.add_column("Intrinsic", justify="right")
    table.add_column("Risk")
    table.add_column("Created")

    for candidate in candidates:
        table.add_row(
            _short(candidate.get("candidate_id")),
            _dash(candidate.get("ticker")),
            _dash(candidate.get("index_code")),
            _format_number(candidate.get("composite_score")),
            _format_percent(candidate.get("safety_margin")),
            _format_money(candidate.get("intrinsic_value")),
            _dash(candidate.get("risk_level")),
            _format_datetime(candidate.get("created_at")),
        )
    return table


def build_candidate_detail(candidate: dict[str, Any]) -> Group:
    """Build compact Rich sections for one candidate detail."""
    snapshot = candidate.get("screening_snapshot") or {}
    if not isinstance(snapshot, dict):
        snapshot = {}

    identity = Table.grid(padding=(0, 2))
    identity.add_column(style="bold")
    identity.add_column()
    identity.add_row("Candidate", _dash(candidate.get("candidate_id")))
    identity.add_row("Ticker", _dash(candidate.get("ticker")))
    identity.add_row("Index", _dash(candidate.get("index_code")))
    identity.add_row("Run", _dash(candidate.get("run_id")))

    score = Table.grid(padding=(0, 2))
    score.add_column(style="bold")
    score.add_column()
    score.add_row("Composite score", _format_number(candidate.get("composite_score")))
    score.add_row("Safety margin", _format_percent(snapshot.get("margin_of_safety")))
    score.add_row("Intrinsic value", _format_money(snapshot.get("intrinsic_value")))
    score.add_row("Risk level", _dash(snapshot.get("risk_level")))

    reasons = _format_list(snapshot.get("reasons") or snapshot.get("candidate_reasons"))
    risks = _format_list(snapshot.get("risk_flags"))

    provenance = Table.grid(padding=(0, 2))
    provenance.add_column(style="bold")
    provenance.add_column()
    provenance.add_row("Created", _format_datetime(candidate.get("created_at")))
    provenance.add_row("Rules version", _dash(snapshot.get("rules_version")))

    return Group(
        Panel(identity, title="Identity"),
        Panel(score, title="Score"),
        Panel(Text(reasons), title="Reasons"),
        Panel(Text(risks), title="Risk Flags"),
        Panel(provenance, title="Provenance"),
    )


def _dash(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _short(value: Any, length: int = 8) -> str:
    text = _dash(value)
    if text == "-" or len(text) <= length:
        return text
    return text[:length]


def _format_indexes(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value) or "-"
    return _dash(value)


def _format_datetime(value: Any) -> str:
    text = _dash(value)
    if text == "-":
        return text
    return text.replace("T", " ")[:19]


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_money(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def _format_list(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value)
