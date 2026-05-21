"""Pytest fixtures for golden dataset loading.

Provides:
- golden_manifest: Parsed manifest.yaml
- golden_stock_ids: List of (ticker, year) tuples for ALL stocks in manifest
- verified_golden_stock_ids: List of (ticker, year) tuples filtered by l3_verified=True
- golden_loader: Callable that loads expected_metrics.yaml for a given ticker/year
- golden_manifest_entries: Dict keyed by ticker for sector/is_financial lookup
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]


GOLDEN_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def golden_manifest() -> dict[str, Any]:
    """Load and return the golden manifest (manifest.yaml).

    Returns:
        Parsed manifest dictionary with ``golden_stocks`` list.
    """
    manifest_path = GOLDEN_DIR / "manifest.yaml"
    content = manifest_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


@pytest.fixture(scope="session")
def golden_stock_ids(golden_manifest: dict[str, Any]) -> list[tuple[str, int]]:
    """Return list of (ticker, year) tuples for ALL stocks in manifest.

    Returns ALL entries regardless of l3_verified status.  This is used
    for test discovery -- the l3_verified flag is used to skip tests,
    not to hide stocks from the fixture.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        List of ``(ticker, year)`` tuples for every manifest entry.
    """
    ids: list[tuple[str, int]] = []
    for entry in golden_manifest["golden_stocks"]:
        for year in entry["years"]:
            ids.append((entry["ticker"], year))
    return ids


@pytest.fixture(scope="session")
def verified_golden_stock_ids(
    golden_manifest: dict[str, Any],
) -> list[tuple[str, int]]:
    """Return list of (ticker, year) tuples ONLY for l3_verified stocks.

    Used by L3 golden tests to parametrize only against fully verified
    entries.  Stocks not yet hand-verified are excluded.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        List of ``(ticker, year)`` tuples where ``l3_verified`` is ``True``.
    """
    ids: list[tuple[str, int]] = []
    for entry in golden_manifest["golden_stocks"]:
        if entry.get("l3_verified", False):
            for year in entry["years"]:
                ids.append((entry["ticker"], year))
    return ids


@pytest.fixture(scope="session")
def golden_loader() -> Any:
    """Return a callable that loads expected_metrics.yaml for a ticker/year.

    Usage::

        def test_moutai(golden_loader):
            metrics = golden_loader("600519.SH", 2023)
            assert metrics["ticker"] == "600519.SH"

    Returns:
        Callable that accepts ``(ticker: str, year: int)`` and returns
        parsed YAML dict.
    """

    def _load(ticker: str, year: int) -> dict[str, Any]:
        path = GOLDEN_DIR / ticker / str(year) / "expected_metrics.yaml"
        if not path.exists():
            msg = f"Golden data not found: {path}"
            raise FileNotFoundError(msg)
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content)

    return _load


@pytest.fixture(scope="session")
def golden_manifest_entries(
    golden_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return dict keyed by ticker of manifest entries.

    Useful for looking up sector and is_financial by ticker.

    Args:
        golden_manifest: Loaded manifest fixture.

    Returns:
        Dict mapping ticker string to its manifest entry dict.
    """
    return {entry["ticker"]: entry for entry in golden_manifest["golden_stocks"]}
