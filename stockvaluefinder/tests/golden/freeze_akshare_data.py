"""Freeze AKShare financial data for golden test datasets.

Fetches income statement, balance sheet, and cash flow data from AKShare
for each stock listed in manifest.yaml and writes the raw JSON responses
to the appropriate golden directory.

Usage:
    # Freeze all stocks in manifest
    uv run python tests/golden/freeze_akshare_data.py

    # Freeze a specific stock
    uv run python tests/golden/freeze_akshare_data.py --ticker 600519.SH

    # Freeze with a different year
    uv run python tests/golden/freeze_akshare_data.py --ticker 600519.SH --year 2023

    # Force overwrite existing frozen data
    uv run python tests/golden/freeze_akshare_data.py --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for imports
GOLDEN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GOLDEN_DIR.parent.parent

# Add project root so stockvaluefinder package is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # type: ignore[import-untyped]  # noqa: E402

from stockvaluefinder.external.akshare_client import eastmoney_hsf10_symbol  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Statement types to fetch: (label, AKShare function name, output filename suffix)
STATEMENT_TYPES: list[tuple[str, str, str]] = [
    ("income", "stock_profit_sheet_by_report_em", "raw_akshare_income.json"),
    ("balance", "stock_balance_sheet_by_report_em", "raw_akshare_balance.json"),
    ("cashflow", "stock_cash_flow_sheet_by_report_em", "raw_akshare_cashflow.json"),
]


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and return the golden manifest YAML.

    Args:
        manifest_path: Path to manifest.yaml.

    Returns:
        Parsed manifest dictionary.

    Raises:
        FileNotFoundError: If manifest file does not exist.
    """
    if not manifest_path.exists():
        msg = f"Manifest not found: {manifest_path}"
        raise FileNotFoundError(msg)
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


def get_stocks_to_freeze(
    manifest: dict[str, Any],
    ticker_filter: str | None,
) -> list[dict[str, Any]]:
    """Determine which stocks to freeze from the manifest.

    Args:
        manifest: Parsed manifest dictionary.
        ticker_filter: Optional single ticker to freeze (e.g. ``"600519.SH"``).

    Returns:
        List of manifest entry dicts to process.
    """
    all_stocks = manifest.get("golden_stocks", [])
    if ticker_filter:
        matched = [s for s in all_stocks if s["ticker"] == ticker_filter]
        if not matched:
            msg = f"Ticker {ticker_filter!r} not found in manifest"
            raise ValueError(msg)
        return matched
    return all_stocks


def freeze_stock(
    ticker: str,
    year: int,
    golden_dir: Path,
    force: bool = False,
) -> tuple[int, list[str]]:
    """Freeze AKShare data for a single stock/year.

    Fetches all three financial statements from AKShare and writes them
    as JSON files with metadata wrappers.

    Args:
        ticker: Stock ticker (e.g. ``"600519.SH"``).
        year: Fiscal year to freeze (e.g. 2023).
        golden_dir: Root golden directory path.
        force: If True, overwrite existing frozen files.

    Returns:
        Tuple of (files_written count, list of errors).
    """
    import akshare as ak  # type: ignore[import-untyped]

    errors: list[str] = []
    files_written = 0
    period = f"{year}1231"
    em_symbol = eastmoney_hsf10_symbol(ticker)
    target_dir = golden_dir / ticker / str(year)
    target_dir.mkdir(parents=True, exist_ok=True)

    for label, func_name, filename in STATEMENT_TYPES:
        target_file = target_dir / filename

        if target_file.exists() and not force:
            logger.info(f"  Skip {ticker}/{filename} (already exists, use --force)")
            files_written += 1
            continue

        try:
            ak_func = getattr(ak, func_name)
            df = ak_func(symbol=em_symbol)

            if df is None or df.empty:
                errors.append(f"{label}: empty response from AKShare")
                logger.warning(f"  {ticker} {label}: empty response")
                continue

            # Filter to target period (keep all periods for multi-year extraction)
            records = df.to_dict("records")

            # Also try period-filtered subset for metadata count
            if "REPORT_DATE" in df.columns:
                col = df["REPORT_DATE"].astype(str)
                dashed = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
                nodash = col.str.replace(r"[^\d]", "", regex=True)
                filtered = df[
                    nodash.str.contains(period, regex=False)
                    | col.str.contains(dashed, regex=False)
                ]
                record_count = len(filtered) if not filtered.empty else len(records)
            else:
                record_count = len(records)

            # Build output with metadata wrapper
            output = {
                "_metadata": {
                    "ticker": ticker,
                    "fiscal_year": year,
                    "period": period,
                    "source": f"akshare.{func_name}",
                    "frozen_date": datetime.now(timezone.utc).isoformat(),
                    "record_count": record_count,
                    "total_records": len(records),
                },
                "records": records,
            }

            target_file.write_text(
                json.dumps(output, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            files_written += 1
            logger.info(
                f"  Froze {ticker}/{filename} ({record_count} period records, {len(records)} total)"
            )

        except Exception as e:
            errors.append(f"{label}: {e}")
            logger.warning(f"  {ticker} {label}: {e}")

    return files_written, errors


def update_manifest_provenance(
    manifest_path: Path,
    frozen_tickers: list[str],
) -> None:
    """Update manifest.yaml provenance status for successfully frozen stocks.

    Changes ``provenance: "pending"`` to ``provenance: "frozen_akshare"``
    for stocks whose data was frozen.

    Args:
        manifest_path: Path to manifest.yaml.
        frozen_tickers: List of ticker strings that were successfully frozen.
    """
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    updated = False

    for entry in manifest["golden_stocks"]:
        if entry["ticker"] in frozen_tickers and entry.get("provenance") == "pending":
            entry["provenance"] = "frozen_akshare"
            updated = True

    if updated:
        manifest_path.write_text(
            yaml.dump(
                manifest, allow_unicode=True, default_flow_style=False, sort_keys=False
            ),
            encoding="utf-8",
        )
        logger.info(
            f"Updated manifest.yaml provenance for {len(frozen_tickers)} stocks"
        )


def main() -> None:
    """CLI entry point for freezing AKShare golden data."""
    parser = argparse.ArgumentParser(
        description="Freeze AKShare financial data for golden test datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s                           Freeze all stocks in manifest
  %(prog)s --ticker 600519.SH        Freeze a single stock
  %(prog)s --year 2022               Use a different fiscal year
  %(prog)s --force                   Overwrite existing frozen files
""",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Freeze a specific ticker instead of all stocks in manifest",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Fiscal year to freeze (default: 2023)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing frozen JSON files",
    )
    args = parser.parse_args()

    start = time.monotonic()
    manifest_path = GOLDEN_DIR / "manifest.yaml"

    try:
        manifest = load_manifest(manifest_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    stocks = get_stocks_to_freeze(manifest, args.ticker)
    logger.info(f"Freezing {len(stocks)} stocks for FY{args.year}")

    total_files = 0
    total_errors: list[str] = []
    frozen_tickers: list[str] = []

    for i, entry in enumerate(stocks):
        ticker = entry["ticker"]
        logger.info(f"[{i + 1}/{len(stocks)}] Freezing {ticker}...")

        files_written, errors = freeze_stock(
            ticker=ticker,
            year=args.year,
            golden_dir=GOLDEN_DIR,
            force=args.force,
        )
        total_files += files_written
        total_errors.extend(errors)

        # Consider frozen if at least some files were written
        if files_written > 0:
            frozen_tickers.append(ticker)

        # Rate limiting: 1 second between stocks
        if i < len(stocks) - 1:
            time.sleep(1.0)

    # Update manifest provenance
    if frozen_tickers:
        update_manifest_provenance(manifest_path, frozen_tickers)

    elapsed = time.monotonic() - start
    logger.info(
        f"Froze {len(frozen_tickers)}/{len(stocks)} stocks "
        f"({total_files} files) in {elapsed:.1f}s"
    )

    if total_errors:
        logger.warning(f"Errors ({len(total_errors)}):")
        for err in total_errors:
            logger.warning(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
