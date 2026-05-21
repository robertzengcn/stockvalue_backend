"""Unit tests for the reconcile CLI (Typer + Rich).

Tests exercise the CLI entry point via ``typer.testing.CliRunner``,
covering exit codes, JSON output structure, single-metric filtering,
verbose mode, and error handling for missing data.

Golden data tests are marked with ``@pytest.mark.golden``.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from stockvaluefinder.tools.reconcile import app

runner = CliRunner()


class TestReconcileCLI:
    """Tests for the ``reconcile`` Typer CLI application."""

    # -- Basic invocation (uses golden data, frozen mode) ---------------------

    @pytest.mark.golden
    def test_cli_basic_invocation(self) -> None:
        """Default invocation with valid ticker/year exits 0 and shows PASS."""
        result = runner.invoke(app, ["--ticker", "600519.SH", "--year", "2023"])
        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
        )
        # Rich renders ANSI; look for either plain PASS or ANSI-wrapped PASS
        output_upper = result.output.upper()
        assert "PASS" in output_upper, (
            f"Expected 'PASS' in output.\nOutput:\n{result.output}"
        )
        # Should mention at least one known metric name
        assert "m_score" in result.output or "dsri" in result.output, (
            f"Expected a known metric name in output.\nOutput:\n{result.output}"
        )

    # -- JSON output ---------------------------------------------------------

    @pytest.mark.golden
    def test_cli_json_output(self) -> None:
        """--json outputs valid JSON with ticker, year, comparisons, summary."""
        result = runner.invoke(
            app,
            ["--ticker", "600519.SH", "--year", "2023", "--json"],
        )
        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
        )
        data = json.loads(result.output)
        assert data["ticker"] == "600519.SH"
        assert data["year"] == 2023
        assert data["p0_all_pass"] is True
        assert len(data["comparisons"]) >= 10, (
            f"Expected >= 10 comparisons, got {len(data['comparisons'])}"
        )
        for cmp in data["comparisons"]:
            assert "metric_name" in cmp
            assert "expected" in cmp
            assert "computed" in cmp
            assert "delta" in cmp
            assert "tolerance" in cmp
            assert "passed" in cmp

    # -- Single metric filter -----------------------------------------------

    @pytest.mark.golden
    def test_cli_single_metric(self) -> None:
        """--metric m_score limits output to a single metric row."""
        result = runner.invoke(
            app,
            ["--ticker", "600519.SH", "--year", "2023", "--metric", "m_score"],
        )
        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
        )
        assert "m_score" in result.output

    # -- Missing ticker -> exit code 2 --------------------------------------

    @pytest.mark.golden
    def test_cli_missing_ticker_exit_code_2(self) -> None:
        """Non-existent ticker returns exit code 2 (error)."""
        result = runner.invoke(app, ["--ticker", "999999.SH", "--year", "2023"])
        assert result.exit_code == 2, (
            f"Expected exit 2 for missing ticker, got {result.exit_code}"
        )

    # -- Verbose mode --------------------------------------------------------

    @pytest.mark.golden
    def test_cli_verbose_mode(self) -> None:
        """--verbose adds PRIORITY column header to the table."""
        result = runner.invoke(
            app,
            ["--ticker", "600519.SH", "--year", "2023", "--verbose"],
        )
        assert result.exit_code == 0, (
            f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
        )
        assert "PRIORITY" in result.output, (
            f"Expected 'PRIORITY' in verbose output.\nOutput:\n{result.output}"
        )

    # -- Full JSON structure validation --------------------------------------

    @pytest.mark.golden
    def test_cli_json_structure_complete(self) -> None:
        """JSON output contains all required top-level and summary keys."""
        result = runner.invoke(
            app,
            ["--ticker", "600519.SH", "--year", "2023", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)

        # Top-level keys
        for key in (
            "ticker",
            "year",
            "summary",
            "skipped_metrics",
            "p0_all_pass",
            "comparisons",
        ):
            assert key in data, f"Missing top-level key: {key}"

        # Summary keys
        summary = data["summary"]
        for key in (
            "total",
            "passed",
            "failed",
            "pass_rate",
            "p0_total",
            "p0_passed",
            "p0_pass_rate",
            "failures",
        ):
            assert key in summary, f"Missing summary key: {key}"

        # skipped_metrics is a list
        assert isinstance(data["skipped_metrics"], list)

    # -- No args shows help --------------------------------------------------

    def test_cli_no_args_shows_help(self) -> None:
        """Invoking with no arguments shows help / error (non-zero exit)."""
        result = runner.invoke(app, [])
        assert result.exit_code != 0, (
            f"Expected non-zero exit with no args, got {result.exit_code}"
        )
        # Typer shows help text mentioning the missing required option
        assert "--ticker" in result.output or "Missing" in result.output, (
            f"Expected help or missing-option message.\nOutput:\n{result.output}"
        )
