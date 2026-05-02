# Phase 8: Task API, Notifications & Sandbox - Discussion Log

**Date:** 2026-05-02
**Phase:** 08-task-api-notifications
**Areas discussed:** SSE Event Design, Manual Trigger API, Sandbox Subprocess, Pipeline Status Endpoint

---

## SSE Event Design

| Question | Selected |
|----------|----------|
| Event storage for replay | ✓ Redis-backed event log (last 100 events, TTL) |
| Event types | ✓ 3 types: task_created, task_completed, task_failed |

---

## Manual Trigger API

| Question | Selected |
|----------|----------|
| Trigger params | ✓ Ticker + optional fiscal_year/report_type |
| Dedup behavior | ✓ Respect dedup, force=true to bypass |
| Pipeline start point | ✓ Full pipeline from download |

---

## Sandbox Subprocess

| Question | Selected |
|----------|----------|
| Execution method | ✓ subprocess.run with resource limits |
| Required/Optional | ✓ Optional with in-process fallback |

---

## Pipeline Status

| Question | Selected |
|----------|----------|
| Status response | ✓ State counts + watcher info (last poll, next poll, total) |

## Deferred Ideas

- Webhook notification — future milestone
- Batch CSI 300 screening — future milestone
