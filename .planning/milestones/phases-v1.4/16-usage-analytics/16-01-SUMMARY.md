---
phase: 16-usage-analytics
plan: 01
subsystem: usage-analytics
tags: [redis, middleware, tracking, orm, migration]
dependency_graph:
  requires: [redis-cache, jwt-auth]
  provides: [usage-tracker, usage-middleware, usage-schemas, api-usage-record-model]
  affects: [dependencies.py, main.py]
tech_stack:
  added: [redis-hashes, redis-pipeline, alembic-018]
  patterns: [per-user-per-endpoint-counters, fire-and-forget-middleware]
key_files:
  created:
    - stockvaluefinder/stockvaluefinder/middleware/usage_tracker.py
    - stockvaluefinder/stockvaluefinder/middleware/usage_middleware.py
    - stockvaluefinder/stockvaluefinder/models/usage.py
    - stockvaluefinder/stockvaluefinder/db/models/api_usage_record.py
    - stockvaluefinder/alembic/versions/018_api_usage_records_table.py
    - stockvaluefinder/tests/unit/test_api/test_usage_tracker.py
  modified:
    - stockvaluefinder/stockvaluefinder/api/dependencies.py
    - stockvaluefinder/stockvaluefinder/main.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py
decisions:
  - Redis Hash keys for per-user usage (usage:{user_id}) with HINCRBY for atomic counters
  - Separate string key for last_active timestamp (usage:last_active:{user_id})
  - 86400s TTL on usage hashes refreshed on each request
  - Error tracking via separate hincrby fields when status_code >= 400
  - Middleware only tracks /api/v1/ paths to avoid noise
  - UsageTracker records are fire-and-forget; Redis failure does not block requests
  - Migration 018 uses composite indexes on (user_id, period_start) and endpoint
metrics:
  duration: 1176s
  completed: 2026-05-11
  tasks: 2
  files_created: 6
  files_modified: 3
  tests: 28
---

# Phase 16 Plan 01: Usage Tracking Foundation Summary

Redis-backed per-user per-endpoint usage tracking with UsageTracker service, HTTP middleware, Pydantic schemas, ORM model, and Alembic migration 018.

## What Was Built

### Task 1: UsageTracker Service + Pydantic Schemas + ORM Model + Migration

**UsageTracker** (`middleware/usage_tracker.py`):
- `record_request(user_id, endpoint, status_code)` atomically increments Redis Hash counters via pipeline
- Per-endpoint call counter: `usage:{user_id}` hash field `calls:{endpoint}`
- Total calls counter: `usage:{user_id}` hash field `total_calls`
- Error tracking: `errors:{endpoint}` and `total_errors` when `status_code >= 400`
- Last-active timestamp: `usage:last_active:{user_id}` string key
- 86400s TTL on usage hash, refreshed on each request
- Graceful degradation on Redis failure (logs warning, does not raise)

**Pydantic Schemas** (`models/usage.py`):
- `EndpointUsage`: endpoint path, call_count, error_count
- `UsageSummary`: user_id, total_calls, total_errors, last_active, endpoints list

**ORM Model** (`db/models/api_usage_record.py`):
- `ApiUsageRecordDB` with UUID PK, user_id FK, endpoint, call_count, error_count, period_start/end, timestamps
- Composite indexes on (user_id, period_start) and endpoint for analytics queries

**Migration 018** (`alembic/versions/018_api_usage_records_table.py`):
- Creates `api_usage_records` table matching the ORM model
- Indexes for user-based and endpoint-based queries

### Task 2: Usage Middleware + Dependencies Init + App Wiring

**Usage Middleware** (`middleware/usage_middleware.py`):
- `usage_tracking_middleware` intercepts HTTP responses after route handlers
- Only tracks `/api/v1/` paths (skips /health, /docs, /, /auth)
- Only tracks authenticated requests (checks `request.state.user_id`)
- Fire-and-forget: Redis write failure does not block the response

**Dependencies** (`api/dependencies.py`):
- `init_usage_tracker(redis)`: Creates UsageTracker, stores module-level, calls `set_usage_tracker`
- `track_usage(request, current_user)`: Sets `request.state.user_id` for middleware consumption

**App Wiring** (`main.py`):
- Usage tracker initialized in lifespan after rate limiter
- `usage_tracking_middleware` registered as HTTP middleware before `rate_limit_headers_middleware`

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| `280b171` | feat(16-01): add UsageTracker service, Pydantic schemas, ORM model, and migration 018 | 6 files |
| `0728170` | feat(16-01): add usage middleware, dependencies init, and wire into app lifespan | 4 files |

## Test Results

- **28 tests** all passing
- 100% coverage on `usage_tracker.py` and `usage.py`
- 92% coverage on `usage_middleware.py` (only exception path uncovered)
- Test breakdown:
  - TestRecordRequest: 8 tests
  - TestGetUserUsage: 3 tests
  - TestGetLastActive: 3 tests
  - TestEndpointUsage: 3 tests
  - TestUsageSummary: 3 tests
  - TestUsageTrackingMiddleware: 5 tests
  - TestInitUsageTracker: 2 tests
  - TestTrackUsageDependency: 1 test

## Deviations from Plan

None - plan executed exactly as written.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-16-01-01 | mitigate | Covered: user_id comes from JWT (not user input), endpoint from request.url.path |
| T-16-01-02 | accept | Accepted: usage data contains user_id and call counts only |
| T-16-01-03 | mitigate | Covered: fire-and-forget in middleware; UsageTracker catches all Redis exceptions |
