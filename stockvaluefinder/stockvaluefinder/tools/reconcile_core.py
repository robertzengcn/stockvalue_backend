"""Stub: reconcile_core module placeholder for TDD RED phase."""

from __future__ import annotations

from typing import Any


def load_manifest() -> dict[str, Any]:
    """Stub."""
    raise NotImplementedError  # type: ignore[unreachable]


def lookup_is_financial(ticker: str) -> bool:
    """Stub."""
    raise NotImplementedError  # type: ignore[unreachable]


def reconcile(ticker: str, year: int, metric: str | None = None) -> Any:
    """Stub."""
    raise NotImplementedError  # type: ignore[unreachable]
