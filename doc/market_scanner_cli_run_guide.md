# Market Scanner CLI Run Guide

This guide shows how to run market scanner operations from the terminal.

Run commands from the backend package directory:

```bash
cd /home/robertzeng/project/stockvalue/stockvalue_backend/stockvaluefinder
```

## 1. Start Local Services

The scanner needs PostgreSQL. Qdrant and Redis are useful for the broader app,
but direct CLI scans do not require Redis or ARQ.

```bash
docker compose up -d postgres qdrant redis
docker compose ps
```

Apply migrations:

```bash
set -a
. ./.env
set +a
export DATABASE_URL="${DATABASE_URL/@postgresql:5433/@localhost:5433}"

uv run alembic upgrade head
```

## 2. Check CLI Help

```bash
uv run stockvalue --help
uv run stockvalue scan --help
```

Expected scanner commands include:

```text
start
run
runs
latest
candidates
candidate
watchlist-add
sync-index
```

## 3. Sync Index Constituents

Before scanning an index, populate `index_constituents`.

```bash
uv run stockvalue scan sync-index --index CSI300
```

JSON output:

```bash
uv run stockvalue scan sync-index --index CSI300 --json
```

Local development fallback:

```bash
DEVELOPMENT_MODE=true uv run stockvalue scan sync-index --index CSI300 --dev-fallback
```

Use `--dev-fallback` only for local smoke tests. It uses a tiny explicit fallback
list if live constituent fetching is unavailable.

## 4. Run a Direct Local Scan

Direct mode uses the existing scanner worker logic without FastAPI, Redis, or
ARQ.

```bash
uv run stockvalue scan run --index CSI300 --type daily --top-n 10 --direct --json
```

Notes:

- `--index` may be repeated.
- `--type` supports `daily` and `weekly`.
- `--top-n` limits the deep-analysis candidate count after coarse screening.
- AKShare bulk quote failures fall back to efinance latest quote data.

## 5. Query Results

API-backed read commands require a running backend and an auth token:

```bash
export STOCKVALUE_API_URL=http://localhost:8000
export STOCKVALUE_TOKEN=<jwt-access-token>

uv run stockvalue scan latest --index CSI300
uv run stockvalue scan candidates --latest --index CSI300 --limit 20
uv run stockvalue scan candidate <candidate-id>
```

For direct local scans without a token, inspect PostgreSQL:

```bash
set -a
. ./.env
set +a
export DATABASE_URL="${DATABASE_URL/@postgresql:5433/@localhost:5433}"

uv run python - <<'PY'
import asyncio
from sqlalchemy import text
from stockvaluefinder.db.base import async_session_maker

async def main():
    async with async_session_maker() as session:
        run = (await session.execute(text("""
            select run_id, status, total_count, screened_count, candidate_count,
                   started_at, completed_at
            from market_scan_runs
            order by created_at desc
            limit 1
        """))).mappings().one()
        print(dict(run))

        candidates = (await session.execute(text("""
            select ticker, index_code, composite_score, screening_snapshot
            from market_scan_candidates
            where run_id = :run_id
            order by composite_score desc
            limit 20
        """), {"run_id": run["run_id"]})).mappings().all()
        for candidate in candidates:
            print(dict(candidate))

asyncio.run(main())
PY
```

## 6. Queued Scan Through API

Queued scans require FastAPI, Redis, ARQ worker, and an admin token.

Start the API:

```bash
uv run uvicorn stockvaluefinder.main:app --reload --host 0.0.0.0 --port 8000
```

Start a scan:

```bash
export STOCKVALUE_API_URL=http://localhost:8000
export STOCKVALUE_TOKEN=<admin-jwt-access-token>

uv run stockvalue scan start --index CSI300 --type daily --top-n 50
```

`scan start` intentionally requires an explicit `--index` to avoid accidental
high-cost scans.

## 7. Current Caveats

The CLI is a thin operational interface over the existing scanner. It does not
change valuation, scoring, or screening rules.

Known scanner-data caveat:

- Current batch market snapshots set `ocf_positive_years=0`.
- The coarse screener requires `min_ocf_positive_years=2`.
- Until OCF history is populated before coarse screening, scans may complete
  with `screened_count=0` and `candidate_count=0`.

Known provider caveat:

- `akshare.stock_zh_a_spot_em()` may fail with `RemoteDisconnected`.
- The scanner falls back to efinance latest quotes when this happens.
