"""L3 live golden tests against real AKShare endpoints.

Runs weekly (not on every PR) to detect upstream data changes or field
renames.  Requires network access and ``DEVELOPMENT_MODE=true``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from stockvaluefinder.external.data_service import ExternalDataService


# ---------------------------------------------------------------------------
# Skip reason for non-development environments
# ---------------------------------------------------------------------------

SKIP_REASON = (
    "Live golden tests require network access and DEVELOPMENT_MODE=true. "
    "Run with: DEVELOPMENT_MODE=true pytest -m golden_live"
)


# ---------------------------------------------------------------------------
# Parametrize helper
# ---------------------------------------------------------------------------


def _load_verified_ids() -> list[tuple[str, int, bool]]:
    """Load verified (ticker, year, is_financial) triples from manifest."""
    manifest_path = Path(__file__).parent / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    ids: list[tuple[str, int, bool]] = []
    for entry in manifest["golden_stocks"]:
        if entry.get("l3_verified", False):
            for year in entry["years"]:
                ids.append((entry["ticker"], year, entry.get("is_financial", False)))
    return ids


_VERIFIED_IDS = _load_verified_ids()
_VERIFIED_IDS_STR = [f"{t}_{y}" for t, y, _ in _VERIFIED_IDS]


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.golden_live
class TestL3GoldenLive:
    """Live AKShare golden tests.  Run weekly to detect upstream data changes."""

    @pytest.mark.parametrize(
        "ticker,year,is_financial",
        _VERIFIED_IDS,
        ids=_VERIFIED_IDS_STR,
    )
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.environ.get("DEVELOPMENT_MODE") != "true",
        reason="Requires DEVELOPMENT_MODE=true to avoid mock data",
    )
    async def test_l3_live_data_fetch(
        self,
        ticker: str,
        year: int,
        is_financial: bool,
    ) -> None:
        """Verify AKShare can fetch data for this ticker/year.

        This test does NOT compare values -- it only verifies that the
        AKShare API returns data for the golden stock.  Value comparison
        is done by the frozen L3 tests after manual data refresh.
        """
        service = ExternalDataService(
            tushare_token="",
            enable_akshare=True,
        )
        await service.initialize()

        report = await service.get_financial_report(ticker, year)

        assert report is not None, f"AKShare returned None for {ticker}/{year}"
        assert report.get("revenue") is not None, (
            f"AKShare report for {ticker}/{year} has no revenue field -- "
            f"possible upstream field rename"
        )
        assert float(report.get("revenue", 0)) != 0.0, (
            f"AKShare report for {ticker}/{year} has zero revenue"
        )
