"""Typer CLI for reconciling computed financial metrics against golden values.

Provides colored Rich table output, JSON mode for CI/CD, verbose audit trail,
and proper exit codes (0=success, 1=P0 failure, 2=error).

Usage::

    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --json
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --verbose
    uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --live
"""

# Stub -- will be implemented in GREEN phase
