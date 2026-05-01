# Phase 6: Smart Watcher - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 06-smart-watcher
**Areas discussed:** Disclosure Source Strategy, Season-Aware Polling Schedule, New Report Detection Logic, Watchlist Management

---

## Disclosure Source Strategy

| Question | Options | Selected |
|----------|---------|----------|
| Primary data source | AKShare only / AKShare + CNInfo fallback / CNInfo direct | ✓ AKShare + CNInfo fallback |
| AKShare failure handling | Fail gracefully / Immediate CNInfo fallback / Async fallback job | ✓ Immediate CNInfo fallback |
| Report types to monitor | All types / Annual + semi-annual / Annual only | ✓ All report types |
| Dedup identification | Construct from poll data / Verify PDF availability | ✓ Construct from poll data |
| Amended report handling | Skip amendments / Reprocess / Log only | ✓ Reprocess amendments |
| Amendment detection | Compare disclosure_date / Compare content hash / Two-stage | ✓ Compare disclosure_date |

**Notes:** User wants comprehensive monitoring (all report types), robust fallback (immediate CNInfo), and amendment reprocessing with date-based detection.

---

## Season-Aware Polling Schedule

| Question | Options | Selected |
|----------|---------|----------|
| Season determination | Month-based in PipelineConfig / Exchange calendar / Fixed daily | ✓ Month-based in PipelineConfig |
| Polling intervals | Daily 09:00 / Weekly Mon 09:00 / 4h+Daily / 2x daily+Weekly | ✓ Daily 09:00 high season, Weekly Mon 09:00 off-season |
| Configuration location | Add to PipelineConfig / Two separate cron jobs | ✓ Add to PipelineConfig |

**Notes:** Simple month-based approach. High season = Jan-Apr daily, off-season = May-Dec weekly. Config-driven for flexibility.

---

## New Report Detection Logic

| Question | Options | Selected |
|----------|---------|----------|
| New vs existing check | Check pipeline_tasks / Timestamp per ticker / Business_key + amendment | ✓ Check pipeline_tasks table |
| Architecture | Single watcher cron / Two-phase poll + process | ✓ Two-phase: poll cron + process job |
| Job granularity | One per disclosure / Batch of N / One per poll cycle | ✓ One job per disclosure |

**Notes:** User prefers decoupled two-phase design. Poll cron writes to staging table, separate worker job processes and enqueues. One job per disclosure for parallelism and failure isolation.

---

## Watchlist Management

| Question | Options | Selected |
|----------|---------|----------|
| Storage | DB table with API / Config file / Config default + DB override | ✓ Database table with API |
| Default population | Auto-seed CSI 300 / Empty by default / All A-shares | ✓ Empty by default, user adds |
| API location | Dedicated watchlist endpoints / Under pipeline routes | ✓ Dedicated watchlist endpoints |
| Watcher state persistence | WatcherState DB table / Logs only / Redis cache | ✓ WatcherState DB table |
| Migration strategy | Single migration 010 / Separate migrations | ✓ Single migration 010 |

**Notes:** User wants explicit control — empty by default, user adds via API. Watcher state tracked in DB for observability. All Phase 6 tables in one migration.

---

## Claude's Discretion

- AKShare client method signatures
- CNInfo HTTP client implementation details
- Staging table schema for pending_disclosures
- Watcher service class structure and error handling
- Logging format and verbosity

## Deferred Ideas

- HKEX monitoring for Hong Kong stocks — future milestone
- Batch import via Excel/text file — nice-to-have, not MVP
- Watchlist groups/tags — not needed for MVP
