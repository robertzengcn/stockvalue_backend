# Phase 5: Pipeline Foundation - Discussion Log

**Date:** 2026-05-01
**Participants:** User, Claude

## Gray Areas Identified

1. Task granularity — monolithic vs one-job-per-state vs micro-jobs
2. Worker deployment — embedded vs separate process
3. Crash recovery — manual retry vs auto-reaper vs TTL-based
4. DB schema design — single table vs two tables vs event-sourced

## Discussion Record

### Area 1: Task Granularity

**Options presented:**
- Monolithic (one job per report)
- One job per state (each stage as separate job)
- Micro-jobs (sub-stages as separate jobs)

**User decision:** One job per state — each pipeline stage (download, parse, analyze) is a separate arq job. Previous job enqueues next on success. Failed jobs retry independently.

**Rationale:** Clean failure isolation — if download fails, parse and analyze don't run. Each stage has different retry characteristics (download = network retry, parse = maybe bad PDF, analyze = service issues). Natural backpressure via arq's job queue.

### Area 2: Worker Deployment

**Options presented:**
- Embedded in FastAPI (same process)
- Separate process (recommended)
- Docker container

**User decision:** Separate process — arq worker runs as independent process alongside FastAPI.

**Rationale:** Process isolation — worker crash doesn't take down API. Independent scaling. Arq is designed for this deployment model. FastAPI only needs the pool for enqueuing.

### Area 3: Crash Recovery

**Options presented:**
- Manual retry (API endpoint)
- Auto-reaper via cron (recommended)
- TTL-based (Redis key expiry)

**User decision:** Auto-reaper via arq cron job.

**Follow-up — reaper timeout:**
- Fixed (30 min)
- Configurable (default 30 min) — **selected**

**Rationale:** Automatic recovery without manual intervention. Configurable timeout accommodates different report sizes. Cron job pattern fits naturally with arq's built-in cron_jobs.

### Area 4: DB Schema Design

**Options presented:**
- Single table (all in pipeline_tasks)
- Two tables: tasks + documents (recommended)
- Event-sourced (state transitions as separate rows)

**User decision:** Two tables — pipeline_tasks (state machine) + pipeline_documents (download metadata).

**Rationale:** Clean separation of concerns. Task state changes frequently (state machine transitions). Document metadata is written once at download time and persists. Document records survive task retries. Enables future queries on document history independent of current task state.

## Decisions Summary

| ID | Area | Decision |
|----|------|----------|
| D-01 | Task granularity | One job per pipeline state |
| D-02 | Task granularity | Job signatures: download_report, parse_report, analyze_report |
| D-03 | Worker deployment | Separate process alongside FastAPI |
| D-04 | Worker deployment | on_startup initializes shared clients in ctx |
| D-05 | Crash recovery | Auto-reaper via arq cron job |
| D-06 | Crash recovery | Stuck tasks reset to PENDING, max_retries limit |
| D-07 | Crash recovery | Timeout configurable via PipelineConfig (default 30 min) |
| D-08 | DB schema | Two tables: pipeline_tasks + pipeline_documents |
| D-09 | DB schema | pipeline_tasks: state machine columns |
| D-10 | DB schema | pipeline_documents: download metadata columns |
| D-11 | DB schema | Single Alembic migration, no existing table changes |

---

*Phase: 05-pipeline-foundation*
*Discussion completed: 2026-05-01*
