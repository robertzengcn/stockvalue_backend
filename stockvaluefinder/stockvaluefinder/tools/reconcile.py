"""Typer CLI for reconciling computed financial metrics against golden values.

Provides colored Rich table output, JSON mode for CI/CD, verbose audit trail,
and proper exit codes (0=success, 1=P0 failure, 2=error).

Usage::

    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --json
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --verbose
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --live
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from stockvaluefinder.tools.reconcile_core import (
    ReconcileResult,
    reconcile,
    reconcile_live,
)
from stockvaluefinder.validation.loader import load_metric_registry

# ---------------------------------------------------------------------------
# Typer application
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="reconcile",
    help="Compare computed financial metrics against golden expected values.",
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_tolerance(absolute: float | None, relative: float | None) -> str:
    """Format tolerance specification as a human-readable string."""
    parts: list[str] = []
    if absolute is not None:
        parts.append(f"abs={absolute}")
    if relative is not None:
        parts.append(f"rel={relative * 100:.1f}%")
    return ", ".join(parts) if parts else "none"


def _format_value(value: float) -> str:
    """Format a numeric value for table display."""
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:.6f}"


def format_rich_table(result: ReconcileResult, verbose: bool = False) -> Table:
    """Build a Rich Table from reconciliation results.

    Args:
        result: ReconcileResult with comparisons to display.
        verbose: If True, add PRIORITY, CATEGORY, AUDIT_TRAIL columns.

    Returns:
        Rich Table object ready for console.print().
    """
    table = Table(
        title=f"Reconcile: {result.ticker} {result.year}",
        show_header=True,
        header_style="bold magenta",
    )

    # Standard columns
    table.add_column("METRIC", style="cyan", no_wrap=True)
    table.add_column("EXPECTED", justify="right")
    table.add_column("COMPUTED", justify="right")
    table.add_column("DELTA", justify="right")
    table.add_column("TOLERANCE", justify="right")
    table.add_column("STATUS", justify="center")

    # Verbose-only columns
    if verbose:
        table.add_column("PRIORITY", justify="center")
        table.add_column("CATEGORY", justify="left")
        table.add_column("AUDIT_TRAIL", justify="center")

    registry = load_metric_registry()

    for cmp in result.comparisons:
        # Look up metric definition for display metadata
        try:
            metric_def = registry.get(cmp.metric_name)
            display_name = metric_def.display_name
            category = metric_def.category
            priority = metric_def.priority
            audit_required = metric_def.audit_trail_required
        except KeyError:
            display_name = cmp.metric_name
            category = "unknown"
            priority = "P2"
            audit_required = False

        # Format numeric values
        expected_str = _format_value(cmp.expected)
        computed_str = _format_value(cmp.computed)
        delta_str = _format_value(cmp.delta)
        tolerance_str = _format_tolerance(
            cmp.tolerance_applied.absolute,
            cmp.tolerance_applied.relative,
        )

        # Status with color
        status = (
            Text("PASS", style="bold green")
            if cmp.passed
            else Text("FAIL", style="bold red")
        )

        # Show both key and display name for grep-ability
        metric_label = (
            f"{cmp.metric_name} ({display_name})"
            if display_name != cmp.metric_name
            else cmp.metric_name
        )

        row: list[str | Text] = [
            metric_label,
            expected_str,
            computed_str,
            delta_str,
            tolerance_str,
            status,
        ]

        if verbose:
            # Color-code priority
            priority_text: str | Text
            if priority == "P0":
                priority_text = Text(priority, style="bold red")
            elif priority == "P1":
                priority_text = Text(priority, style="yellow")
            else:
                priority_text = priority

            row.append(priority_text)
            row.append(category)
            row.append("Yes" if audit_required else "No")

        table.add_row(*row)

    return table


def format_json_output(result: ReconcileResult) -> str:
    """Build machine-parseable JSON from reconciliation results.

    Args:
        result: ReconcileResult to serialize.

    Returns:
        JSON string with ticker, year, summary, comparisons, skipped metrics.
    """
    output = {
        "ticker": result.ticker,
        "year": result.year,
        "summary": result.summary,
        "skipped_metrics": result.skipped_metrics,
        "p0_all_pass": result.p0_all_pass,
        "comparisons": [
            {
                "metric_name": c.metric_name,
                "expected": c.expected,
                "computed": c.computed,
                "delta": c.delta,
                "tolerance": {
                    "absolute": c.tolerance_applied.absolute,
                    "relative": c.tolerance_applied.relative,
                },
                "passed": c.passed,
            }
            for c in result.comparisons
        ],
    }
    return json.dumps(output, indent=2)


def format_verbose_output(result: ReconcileResult) -> str:
    """Build detailed audit trail text for each metric comparison.

    Printed after the Rich table when ``--verbose`` is active.

    Args:
        result: ReconcileResult with comparisons to detail.

    Returns:
        Multi-line string with per-metric breakdowns.
    """
    registry = load_metric_registry()
    lines: list[str] = []

    lines.append("")
    lines.append("=" * 72)
    lines.append("AUDIT TRAIL BREAKDOWN")
    lines.append("=" * 72)

    for cmp in result.comparisons:
        try:
            metric_def = registry.get(cmp.metric_name)
            display_name = metric_def.display_name
            category = metric_def.category
            priority = metric_def.priority
            audit_required = metric_def.audit_trail_required
            formula_ref = metric_def.formula_ref
        except KeyError:
            display_name = cmp.metric_name
            category = "unknown"
            priority = "P2"
            audit_required = False
            formula_ref = None

        status_str = "PASS" if cmp.passed else "FAIL"
        lines.append("")
        lines.append(
            f"  [{priority}] {display_name} ({cmp.metric_name}) - {status_str}"
        )
        lines.append(f"    Category:    {category}")
        lines.append(f"    Expected:    {cmp.expected:.6f}")
        lines.append(f"    Computed:    {cmp.computed:.6f}")
        lines.append(f"    Delta:       {cmp.delta:.6f}")
        lines.append(
            f"    Tolerance:   {_format_tolerance(cmp.tolerance_applied.absolute, cmp.tolerance_applied.relative)}"
        )
        if formula_ref:
            lines.append(f"    Formula ref: {formula_ref}")
        if audit_required:
            lines.append("    Audit trail: available (see calculation logs)")
            lines.append(
                "    Note: numerator/denominator breakdown available "
                "in calculation function audit trail dicts"
            )
        lines.append("    Depends on:  (see registry for upstream metrics)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command()
def main(
    ticker: str = typer.Option(..., help="Stock ticker (e.g. 600519.SH)"),
    year: int = typer.Option(..., help="Fiscal year (e.g. 2023)"),
    metric: Optional[str] = typer.Option(
        None, "--metric", help="Limit to single metric"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full audit trail breakdown"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-parseable JSON"
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Fetch live data from AKShare (default: use frozen golden data)",
    ),
) -> None:
    """Compare computed financial metrics against golden expected values."""
    # Use a wide console to avoid Rich truncating column headers in verbose mode
    console = Console(width=200 if verbose else None)
    err_console = Console(stderr=True, width=200)

    # --- Run reconciliation ---
    try:
        if live:
            result = asyncio.run(reconcile_live(ticker, year, metric))
        else:
            result = reconcile(ticker, year, metric)
    except FileNotFoundError as exc:
        # Sanitize path: strip absolute filesystem paths from error message
        # Keep only the relative portion starting from "tests/"
        msg = str(exc)
        marker = "tests/"
        idx = msg.find(marker)
        if idx > 0:
            # Find the part before "tests/" in the message and strip the path prefix
            prefix = msg[:idx]
            # Find where the path starts in the prefix
            path_marker = "Expected: "
            path_idx = prefix.find(path_marker)
            if path_idx >= 0:
                msg = prefix[: path_idx + len(path_marker)] + msg[idx:]
        err_console.print(f"[bold red]Error:[/bold red] {msg}")
        raise typer.Exit(code=2) from None
    except KeyError as exc:
        err_console.print(f"[bold red]Error:[/bold red] Unknown metric: {exc}")
        raise typer.Exit(code=2) from None
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from None

    # --- Output ---
    if json_output:
        console.print(format_json_output(result))
    else:
        console.print(format_rich_table(result, verbose=verbose))
        if verbose:
            console.print(format_verbose_output(result))

        # Summary line
        summary = result.summary
        p0_passed = summary.get("p0_passed", 0)
        p0_total = summary.get("p0_total", 0)
        p0_pass_rate = summary.get("p0_pass_rate", 0.0)
        total_passed = summary.get("passed", 0)
        total_count = summary.get("total", 0)

        console.print(
            f"\nP0: {p0_passed}/{p0_total} passed ({p0_pass_rate:.1f}%) "
            f"| Total: {total_passed}/{total_count} passed"
        )

        if result.skipped_metrics:
            console.print(
                f"Skipped {len(result.skipped_metrics)} metrics: "
                f"{', '.join(result.skipped_metrics)}"
            )

    # --- Exit code ---
    exit_code = 0 if result.p0_all_pass else 1
    raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# Entry point for ``python -m``
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
