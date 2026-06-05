"""Unit tests for market scanner CLI output formatters."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from rich.console import Console

from stockvaluefinder.tools.scanner_formatters import (
    build_candidate_detail,
    build_candidate_table,
    build_run_table,
    format_json,
)


def _render(obj: object) -> str:
    console = Console(record=True, force_terminal=False, width=120)
    console.print(obj)
    return console.export_text()


def test_run_table_renders_expected_columns() -> None:
    """Run table includes the PRD columns."""
    table = build_run_table(
        [
            {
                "run_id": "run-1",
                "index_codes": ["CSI300", "CSI500"],
                "scan_type": "daily",
                "status": "completed",
                "total_count": 800,
                "screened_count": 120,
                "candidate_count": 20,
                "started_at": "2026-06-05T10:00:00",
                "completed_at": "2026-06-05T10:05:00",
            }
        ]
    )

    output = _render(table)

    for column in ("Run ID", "Indexes", "Type", "Status", "Total", "Candidates"):
        assert column in output
    assert "CSI300,CSI500" in output


def test_candidate_table_renders_missing_optional_fields_as_dash() -> None:
    """Missing optional candidate fields render as '-'."""
    table = build_candidate_table(
        [
            {
                "ticker": "600519.SH",
                "index_code": "CSI300",
                "composite_score": 82.4,
                "safety_margin": None,
                "intrinsic_value": None,
                "risk_level": None,
                "created_at": None,
            }
        ]
    )

    output = _render(table)

    assert "Ticker" in output
    assert "600519.SH" in output
    assert "-" in output


def test_candidate_detail_includes_reasons_risks_and_provenance() -> None:
    """Candidate detail includes identity, scoring, reasons, risk flags, provenance."""
    detail = build_candidate_detail(
        {
            "candidate_id": "candidate-1",
            "run_id": "run-1",
            "ticker": "600519.SH",
            "index_code": "CSI300",
            "composite_score": 88.2,
            "created_at": "2026-06-05T10:00:00",
            "screening_snapshot": {
                "margin_of_safety": 0.382,
                "intrinsic_value": 1850.0,
                "risk_level": "LOW",
                "reasons": ["wide margin of safety"],
                "risk_flags": ["customer concentration"],
                "rules_version": "v1",
            },
        }
    )

    output = _render(detail)

    assert "600519.SH" in output
    assert "wide margin of safety" in output
    assert "customer concentration" in output
    assert "v1" in output


def test_format_json_serializes_uuid_and_datetime() -> None:
    """JSON output serializes UUID and datetime values with default=str."""
    payload = {
        "run_id": UUID("00000000-0000-0000-0000-000000000001"),
        "created_at": datetime(2026, 6, 5, 10, 0, 0),
    }

    data = json.loads(format_json(payload))

    assert data["run_id"] == "00000000-0000-0000-0000-000000000001"
    assert data["created_at"] == "2026-06-05 10:00:00"
