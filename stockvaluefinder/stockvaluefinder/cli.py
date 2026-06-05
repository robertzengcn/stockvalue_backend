"""Top-level StockValueFinder command line interface."""

from __future__ import annotations

import typer

from stockvaluefinder.tools.scanner_cli import app as scanner_app

app = typer.Typer(name="stockvalue", help="StockValueFinder command line tools.")
app.add_typer(scanner_app, name="scan", help="Market scanner operations.")


if __name__ == "__main__":
    app()
