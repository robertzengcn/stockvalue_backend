"""Index constituent synchronization helpers for scanner CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.models.market_scanner import IndexConstituentCreate
from stockvaluefinder.repositories.index_constituent_repo import (
    IndexConstituentRepository,
)

INDEX_SYMBOLS = {
    "CSI300": "000300",
    "CSI500": "000905",
}

DEV_FALLBACK_CONSTITUENTS = {
    "CSI300": [
        ("600519.SH", "贵州茅台"),
        ("000001.SZ", "平安银行"),
        ("601318.SH", "中国平安"),
    ],
    "CSI500": [
        ("600884.SH", "杉杉股份"),
        ("000027.SZ", "深圳能源"),
        ("600873.SH", "梅花生物"),
    ],
}


@dataclass(frozen=True)
class SyncIndexResult:
    """Summary of an index constituent sync operation."""

    index_code: str
    source: str
    upserted_count: int
    deactivated_count: int


async def sync_index_constituents(
    index_code: str,
    use_dev_fallback: bool = False,
) -> SyncIndexResult:
    """Fetch and persist active constituents for a supported index."""
    normalized = index_code.strip().upper()
    if normalized not in INDEX_SYMBOLS:
        raise ValueError(
            f"Unsupported index '{index_code}'. Supported: {sorted(INDEX_SYMBOLS)}"
        )

    source = "akshare"
    try:
        rows = await _fetch_akshare_constituents(normalized)
    except Exception as exc:
        if not use_dev_fallback:
            raise ValueError(
                f"Failed to fetch {normalized} constituents: {exc}"
            ) from exc
        rows = _dev_fallback_rows(normalized)
        source = "dev-fallback"

    if not rows and use_dev_fallback:
        rows = _dev_fallback_rows(normalized)
        source = "dev-fallback"
    if not rows:
        raise ValueError(f"No constituents returned for {normalized}.")

    effective_date = date.today()
    models = [
        IndexConstituentCreate(
            constituent_id=uuid4(),
            index_code=normalized,
            ticker=ticker,
            name=name,
            effective_date=effective_date,
            is_active=True,
        )
        for ticker, name in rows
    ]

    async with async_session_maker() as session:
        repo = IndexConstituentRepository(session)
        await repo.bulk_upsert_constituents(models)
        deactivated = await repo.deactivate_missing(
            normalized,
            {model.ticker for model in models},
            effective_date,
        )
        await session.commit()

    return SyncIndexResult(
        index_code=normalized,
        source=source,
        upserted_count=len(models),
        deactivated_count=deactivated,
    )


async def _fetch_akshare_constituents(index_code: str) -> list[tuple[str, str]]:
    client = AKShareClient()
    await client.check_available()
    rows = await client.get_index_constituents(INDEX_SYMBOLS[index_code])
    parsed: list[tuple[str, str]] = []
    for row in rows:
        item = _parse_constituent_row(row)
        if item is not None:
            parsed.append(item)
    return parsed


def _parse_constituent_row(row: dict[str, Any]) -> tuple[str, str] | None:
    code = _first_present(
        row,
        "成分券代码",
        "品种代码",
        "证券代码",
        "代码",
        "cons_code",
        "code",
    )
    name = _first_present(
        row,
        "成分券名称",
        "品种名称",
        "证券简称",
        "名称",
        "name",
    )
    if code is None:
        return None
    ticker = _to_ticker(str(code))
    if ticker is None:
        return None
    return ticker, str(name or ticker)


def _first_present(row: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _to_ticker(code: str) -> str | None:
    cleaned = code.strip().upper()
    if "." in cleaned:
        base, suffix = cleaned.split(".", maxsplit=1)
        if suffix in {"SH", "SZ"} and base.isdigit():
            return f"{base.zfill(6)}.{suffix}"
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) != 6:
        return None
    if digits.startswith("6"):
        return f"{digits}.SH"
    if digits.startswith(("0", "3")):
        return f"{digits}.SZ"
    return None


def _dev_fallback_rows(index_code: str) -> list[tuple[str, str]]:
    if os.getenv("DEVELOPMENT_MODE", "false").lower() != "true":
        raise ValueError("--dev-fallback requires DEVELOPMENT_MODE=true.")
    return list(DEV_FALLBACK_CONSTITUENTS[index_code])
