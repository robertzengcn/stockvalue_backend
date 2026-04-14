# Additional Financial Analysis — Technology Advice

This note complements [Additional_Financial_Analysis_Advice.md](./Additional_Financial_Analysis_Advice.md) (product priorities and formulas) with implementation guidance aligned with this backend: `models/` → `services/` → `repositories/` → `api/`, `ApiResponse` in `models/api.py`, and external data via `external/data_service.py`.

---

## Architecture and placement

- **Keep all of these as deterministic Python** (pure functions or small service methods). Do not route numeric ratio work through LLM agents; agents can summarize *after* numbers exist, consistent with the platform principle that financial arithmetic stays in code.
- **Prefer one “fundamentals” or “quality” surface area** rather than many micro-endpoints: e.g. a single `POST /api/v1/analyze/fundamentals/` (or `.../financial-health/`) returning a structured DTO with optional sections, *or* extend `risk` only if Z-Score and debt metrics should stay tightly coupled to fraud/bankruptcy narrative. Splitting later is easier than merging fragmented APIs.
- **Separate “inputs snapshot” from “derived metrics”** in the response: store or return raw inputs used (EBIT, working capital, total assets, etc.) so the UI and audits can explain the score without re-fetching.

---

## Data and correctness

- **Time-series vs point-in-time**: DuPont, FCF quality, earnings stability, and payout trends need **aligned fiscal periods** and clear rules for TTM vs annual. Define one canonical “statement row” model per metric (e.g. last 5 annual + optional TTM) and document gaps (delisting, restatements).
- **A-share vs H-share**: Ratios that use **market cap** (Altman Z for listed firms) and **shares outstanding** must use the same currency and share class; HK listings are where subtle bugs hide.
- **Edge cases in code, not in prose**: Graham number with negative BVPS, zero or negative EPS, missing interest expense (coverage undefined), EBITDA ≤ 0 (debt/EBITDA sentinel). Return `null` plus a machine-readable `reason` per field rather than fake numbers.
- **Model variants**: Altman Z has **public vs private** formulations; pick one, name it in the API (e.g. `z_score_variant: "altman_public"`), and unit-test against published examples so variants can be swapped without breaking clients.

---

## API, schema, and evolution

- **Version fields inside `data`**, not only URL versioning: e.g. `engine_version`, `formula_version`, `as_of` (price date vs statement date). Financial screens go stale quickly; clients need to know what they are looking at.
- **Envelope stays stable**; extend `meta` for timing, cache hit, data source (`akshare`/`tushare`), and partial failures (e.g. “PEG omitted: no growth estimate”).
- **Contract tests** (`tests/contract/`) should lock request/response shapes for the new endpoint the same way as risk/yield/valuation.

---

## Performance and operations

- **Batch CSI 300**: For screening, add an internal job path (queue or cron) that writes results to DB and serves dashboards from stored scores; avoid hammering upstream APIs from interactive UI for 300 tickers. “Earnings stability” style metrics assume this pattern.
- **Caching**: Reuse caching utilities for expensive fetches; cache key should include **ticker + fiscal period + data source version**. Invalidate on major corporate actions if event hooks are added later.
- **Idempotency**: Same ticker + same inputs should produce the same outputs for a given `as_of`; helps testing and regression detection.

---

## Testing strategy

- **Golden-vector tests** for Z-Score, DuPont, Graham: small tables of inputs → expected outputs (rounded), including grey-zone boundaries from the product doc.
- **Property-style checks** where easy: e.g. DuPont product ≈ ROE within tolerance after rounding rules are fixed.
- **Data gap tests**: missing interest, missing CFO years — response should degrade gracefully with explicit omissions.

---

## Frontend integration

- Mirror new DTOs in `stockvalue_frontend` `api/types.ts` and treat each metric as **nullable + reason** so the UI can show “N/A” with tooltip text instead of silent zeros.

---

## Optional later: sandbox

If you eventually expose **user-defined formulas** or scripting, `services/calculation_sandbox.py` is the right place — but for the analyses in the product doc, **plain Python in services** is simpler, safer, and easier to test than a sandbox until user code is truly required.

---

## Design follow-up

Choose explicitly whether to ship **one combined fundamentals endpoint** or **fold Z-Score/debt into `/analyze/risk/`** — that drives DTO shape and which repository methods to extend first.
