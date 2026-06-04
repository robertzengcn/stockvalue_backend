# Phase 16: Usage Analytics - Research

**Researched:** 2026-05-11
**Domain:** Redis-based API usage tracking, periodic DB persistence, admin analytics endpoints, per-user rate limit configuration
**Confidence:** HIGH

## Summary

Phase 16 implements usage analytics by tracking every authenticated API call per user per endpoint using Redis counters, persisting aggregated data to PostgreSQL on a periodic basis, and exposing admin endpoints for viewing usage summaries and aggregate statistics. It also implements per-user rate limit overrides (RATE-04), which requires extending the existing `RateLimiter` class.

The system already has a mature Redis integration through `CacheManager` (utils/cache.py) and `RateLimiter` (middleware/rate_limiter.py) using `INCR` + `EXPIRE`. The usage tracker should follow the same atomic Redis counter pattern. A new `api_usage_records` DB table with an Alembic migration (018) is needed for persistence. A FastAPI HTTP middleware can intercept all authenticated requests to record usage non-blockingly. A background task (asyncio or arq) should periodically flush Redis counters to PostgreSQL and clear the Redis keys.

**Primary recommendation:** Use a FastAPI HTTP middleware for tracking, Redis Hash counters per user (HINCRBY for per-endpoint counts, SET for last_active timestamp), a new `api_usage_records` ORM model with Alembic migration 018 for persistence, and an asyncio background task spawned during lifespan for periodic flushing. Extend the existing `RateLimiter` to support per-user overrides via a `user_rate_limits` Redis Hash or a DB table.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLY-01 | System tracks API call count per user per endpoint | Redis HINCRBY per user hash with endpoint field; FastAPI HTTP middleware |
| ANLY-02 | System tracks last active timestamp per user | Redis SET with timestamp string per user; updated on every request |
| ANLY-03 | Admin can view usage summary per user (call counts, last active) | New admin GET endpoint reading from Redis (hot) + DB (historical) |
| ANLY-04 | Admin can view aggregate usage stats (total calls, top users, error rates) | New admin GET endpoint with SQL aggregation on persisted data + Redis SCAN |
| ANLY-05 | Usage data stored in Redis with periodic DB flush for persistence | asyncio background task in lifespan; new `api_usage_records` DB table |
| RATE-04 | Admin can adjust rate limits per user | Extend RateLimiter with per-user override lookup from Redis Hash or DB table |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Request interception and counting | API Server (FastAPI Middleware) | -- | Middleware sees all requests before route handlers |
| Real-time counter storage | Redis | -- | Atomic INCR/HINCRBY is O(1); ephemeral counters ideal for Redis |
| Last-active timestamp | Redis | -- | Simple SET per user, read on admin query |
| Periodic persistence | Background Task (asyncio) | PostgreSQL | Flush Redis counters to DB on configurable interval |
| Historical usage queries | PostgreSQL | -- | SQL aggregation for totals, top users, time ranges |
| Per-user rate limit overrides | Redis + PostgreSQL | -- | Override stored in Redis for fast lookup, DB for persistence |
| Admin analytics endpoints | API Server (FastAPI Routes) | -- | Standard REST endpoints with require_admin dependency |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| redis | 7.2.1 | Counter storage, per-user hashes, last_active | Already in project; atomic HINCRBY, SET operations |
| sqlalchemy | 2.0.47 | ORM for api_usage_records table | Already in project; async ORM with PostgreSQL |
| alembic | 1.18.4 | Database migration for new tables | Already in project; next migration is 018 |
| pydantic | 2.12.5 | Request/response schemas for analytics | Already in project; frozen BaseModel pattern |
| fastapi | 0.133.1 | HTTP middleware + admin routes | Already in project; middleware + APIRouter |
| asyncpg | 0.31.0 | PostgreSQL async driver | Already in project; used by SQLAlchemy async |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit + integration tests | All test files |
| pytest-asyncio | (installed) | Async test support | Testing async services and routes |
| pytest-mock | 3.15.1 | Mock Redis, DB sessions | Isolating analytics service from Redis/DB |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Redis Hash per user | Redis Sorted Set per endpoint | Hash is simpler for per-user-per-endpoint; ZSET better for leaderboard queries but overkill |
| asyncio background task | arq worker (already in project) | arq is heavier (needs Redis for task queue); asyncio task is simpler for a periodic flush every N seconds |
| HTTP middleware | Dependency-based tracking per route | Middleware is centralized and automatic; dependency approach requires manual wiring on every route (error-prone) |
| Single `api_usage_records` table | Separate `api_usage_hourly` + `api_usage_daily` tables | Single table is simpler for MVP; can pre-aggregate later if volume demands it |

**Installation:**
No new packages needed. All dependencies already in pyproject.toml.

**Version verification:**
Verified from venv:
- redis: 7.2.1 (via `.venv/bin/python`)
- sqlalchemy: 2.0.47
- pydantic: 2.12.5
- fastapi: 0.133.1
- alembic: 1.18.4
- asyncpg: 0.31.0
- pytest: 9.0.2

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
    |
    v
[FastAPI HTTP Middleware: usage_tracker_middleware]
    |-- Extract user_id from JWT (if authenticated)
    |-- Redis HINCRBY "usage:{user_id}" {endpoint_path} 1
    |-- Redis SET "usage:last_active:{user_id}" {timestamp}
    |
    v
[Route Handler] --> [Response]
    |                        |
    |                        v
    |               [Middleware records error status if 4xx/5xx]
    |
    v
[Background Task (lifespan-spawned asyncio)]
    |-- Every 300 seconds (configurable):
    |   1. SCAN Redis for "usage:*" keys
    |   2. HGETALL per user hash -> build ApiUsageRecord
    |   3. Bulk upsert into PostgreSQL api_usage_records
    |   4. DELETE processed Redis keys
    |
    v
[PostgreSQL: api_usage_records table]
    |-- Columns: user_id, endpoint, call_count, error_count, period_start, period_end
    |-- Queried by admin analytics endpoints
    |
    v
[Admin Analytics Routes]
    |-- GET /api/v1/admin/analytics/users/{user_id}  (ANLY-03)
    |-- GET /api/v1/admin/analytics/aggregate          (ANLY-04)
    |-- GET /api/v1/admin/analytics/users/{user_id}/rate-limit (RATE-04)
    |-- PUT /api/v1/admin/analytics/users/{user_id}/rate-limit (RATE-04)
```

### Recommended Project Structure
```
stockvaluefinder/
  middleware/
    rate_limiter.py           # EXISTING - extend with per-user override support
    usage_tracker.py          # NEW - UsageTracker class (Redis HINCRBY logic)
  api/
    admin_routes.py           # EXISTING - add analytics + rate limit config endpoints
    analytics_routes.py       # NEW - dedicated analytics admin routes
    dependencies.py           # EXISTING - add init_usage_tracker, get_usage_tracker
  repositories/
    usage_repo.py             # NEW - ApiUsageRepository for persisted analytics data
    rate_limit_override_repo.py  # NEW - per-user rate limit override CRUD
  models/
    usage.py                  # NEW - Pydantic schemas for analytics
    rate_limit_config.py      # NEW - Pydantic schemas for rate limit overrides
  db/models/
    api_usage_record.py       # NEW - SQLAlchemy ORM model
    rate_limit_override.py    # NEW - SQLAlchemy ORM model for per-user overrides
  services/
    usage_flush_service.py    # NEW - background flush logic (Redis -> DB)
```

### Pattern 1: Redis Hash for Per-User-Per-Endpoint Counters
**What:** Use Redis Hash where key = `usage:{user_id}` and field = `{endpoint_path}`, value = count
**When to use:** Tracking API call counts per user per endpoint in real-time
**Example:**
```python
# Source: [VERIFIED: codebase pattern from middleware/rate_limiter.py Redis INCR]
class UsageTracker:
    """Track API usage per user per endpoint using Redis Hashes."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _build_usage_key(self, user_id: str) -> str:
        return f"usage:{user_id}"

    def _build_last_active_key(self, user_id: str) -> str:
        return f"usage:last_active:{user_id}"

    async def record_request(
        self, user_id: str, endpoint: str, status_code: int
    ) -> None:
        """Record a request atomically. Non-blocking, fire-and-forget style."""
        pipe = self._redis.pipeline()
        key = self._build_usage_key(user_id)
        # Increment endpoint counter
        pipe.hincrby(key, f"calls:{endpoint}", 1)
        # Increment total counter
        pipe.hincrby(key, "total_calls", 1)
        # Track errors
        if status_code >= 400:
            pipe.hincrby(key, f"errors:{endpoint}", 1)
            pipe.hincrby(key, "total_errors", 1)
        # Update last active
        last_active_key = self._build_last_active_key(user_id)
        pipe.set(last_active_key, str(int(time.time())))
        # Set TTL on usage hash (e.g., 24 hours for auto-cleanup)
        pipe.expire(key, 86400)
        await pipe.execute()
```

### Pattern 2: FastAPI HTTP Middleware for Automatic Tracking
**What:** A Starlette-style HTTP middleware that intercepts all requests
**When to use:** When every authenticated request needs tracking without manual wiring
**Example:**
```python
# Source: [VERIFIED: codebase pattern from main.py rate_limit_headers_middleware]
@app.middleware("http")
async def usage_tracking_middleware(request: Request, call_next):
    """Track API usage for authenticated users."""
    response = await call_next(request)

    # Only track if user identity is available (via request.state or JWT extraction)
    # Skip health, root, auth endpoints
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id
        endpoint = request.url.path
        status_code = response.status_code
        # Fire-and-forget: don't await, let it run in background
        if _usage_tracker is not None:
            asyncio.create_task(
                _usage_tracker.record_request(user_id, endpoint, status_code)
            )

    return response
```

### Pattern 3: Background Flush Task in Lifespan
**What:** Spawn an asyncio task during application lifespan that periodically flushes Redis to DB
**When to use:** Periodic persistence of ephemeral Redis counters to durable PostgreSQL
**Example:**
```python
# Source: [VERIFIED: codebase pattern from main.py lifespan context manager]
async def _usage_flush_loop(
    redis: Redis, db_session_factory, interval_seconds: int = 300
):
    """Background coroutine that periodically flushes Redis usage data to DB."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            # SCAN for usage:* keys
            # HGETALL each hash
            # Bulk upsert into api_usage_records
            # DELETE processed keys
            pass
        except Exception as e:
            logger.warning(f"Usage flush failed: {e}")
```

### Pattern 4: Per-User Rate Limit Override
**What:** Store per-user rate limit overrides that the RateLimiter checks before using defaults
**When to use:** RATE-04 requirement for admin-adjustable per-user limits
**Example:**
```python
# Source: [VERIFIED: codebase pattern from middleware/rate_limiter.py]
class RateLimiter:
    async def check_rate_limit(self, user_id: str, ...):
        # Check for per-user override
        override = await self._get_user_override(user_id)
        effective_limit = override.limit if override else self._default_limit
        effective_window = override.window if override else self._window_seconds
        # ... rest of existing logic

    async def _get_user_override(self, user_id: str):
        """Look up per-user rate limit override from Redis Hash."""
        key = f"rate_limit_override:{user_id}"
        data = await self._redis.hgetall(key)
        if data:
            return RateLimitOverride(
                limit=int(data[b"limit"]),
                window=int(data[b"window"]),
            )
        return None
```

### Anti-Patterns to Avoid
- **Tracking in dependency injection instead of middleware:** Forgetting to add tracking dependency on new routes; middleware is centralized and automatic
- **Blocking the request on Redis write:** Usage tracking must be fire-and-forget (asyncio.create_task) to avoid adding latency to API responses
- **Flushing all Redis keys:** Only flush `usage:*` keys, not `rate_limit:*` or cache keys
- **Per-request DB writes for analytics:** Writing to PostgreSQL on every request kills performance; always buffer in Redis first
- **Storing raw request/response bodies:** Only track endpoint path, status code, and timestamp; never store request payloads in analytics

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic counters | Custom locking in Python | Redis HINCRBY (atomic, O(1)) | Race conditions with concurrent requests |
| Periodic background tasks | Custom threading/timer | asyncio.create_task in lifespan | No extra dependencies; integrates with FastAPI lifecycle |
| Key scanning in Redis | KEYS command (blocks Redis) | SCAN iterator | KEYS blocks the Redis event loop; SCAN is incremental |
| Rate limit override storage | Custom in-memory dict | Redis Hash (persisted) + DB table | Survives restarts; shared across workers |

**Key insight:** The existing `RateLimiter` already uses Redis INCR + EXPIRE atomically. Usage tracking reuses the same Redis instance and atomic patterns. Do not create a second Redis connection -- use `cache.redis` from the existing `CacheManager`.

## Common Pitfalls

### Pitfall 1: Middleware Cannot Access JWT User Identity
**What goes wrong:** HTTP middleware runs before `Depends(get_current_user)` resolves, so `request.state` has no user_id
**Why it happens:** FastAPI dependency injection happens inside route handlers, not in middleware
**How to avoid:** Either (a) decode JWT in middleware directly (duplicating auth logic), or (b) set user_id in request.state from within a shared dependency that runs on protected routes, then have the middleware read it on response. Approach (b) is cleaner: create a `track_usage` dependency that sets `request.state.user_id` and is added to all protected routes, then middleware reads it after `call_next`.
**Warning signs:** Analytics always shows zero usage; middleware logs show `user_id=None`

### Pitfall 2: Redis Key Explosion
**What goes wrong:** Creating separate keys for every user+endpoint combination fills Redis memory
**Why it happens:** Using individual string keys per counter instead of hashes
**How to avoid:** Use Redis Hash per user: key=`usage:{user_id}`, fields = endpoint counters. One key per user, not per user+endpoint.
**Warning signs:** `INFO memory` shows rapid growth; `DBSIZE` grows linearly with users * endpoints

### Pitfall 3: Race Condition During Flush
**What goes wrong:** Flush reads counters, deletes keys; concurrent request increments counter between read and delete; count is lost
**Why it happens:** Non-atomic read-then-delete of Redis keys
**How to avoid:** Use RENAME to atomically swap the usage hash before reading: rename `usage:{user_id}` to `usage_flush:{user_id}`, then read and delete the flush key. New requests write to the original key. Alternatively, use a Lua script for atomic read+reset.
**Warning signs:** Periodic flush counts are lower than expected; discrepancies between Redis total and DB total

### Pitfall 4: Background Task Dies Silently
**What goes wrong:** The asyncio background flush task crashes (e.g., DB connection error) and never restarts
**Why it happens:** Unhandled exception in the while-True loop kills the coroutine
**How to avoid:** Wrap the flush body in try/except, log the error, and continue the loop. Add health-check logging (e.g., "Flush completed: N records written") to detect staleness.
**Warning signs:** No "Flush completed" logs for extended periods; DB table has no new rows

### Pitfall 5: Admin Analytics Query Performance
**What goes wrong:** Aggregate stats query does full table scan on api_usage_records
**Why it happens:** Missing indexes on user_id, period_start, endpoint columns
**How to avoid:** Add indexes on (user_id), (period_start), (user_id, period_start), (endpoint) in the Alembic migration.
**Warning signs:** Admin analytics endpoint takes >2 seconds to respond; pg_stat_activity shows long-running queries

## Code Examples

Verified patterns from codebase:

### Redis Atomic Increment (existing pattern)
```python
# Source: [VERIFIED: stockvaluefinder/middleware/rate_limiter.py lines 84-100]
# Existing RateLimiter pattern -- usage tracker reuses this atomic INCR approach
count = await self._redis.incr(key)
if count == 1:
    await self._redis.expire(key, effective_window)
```

### Admin Route with require_admin (existing pattern)
```python
# Source: [VERIFIED: stockvaluefinder/api/admin_routes.py lines 48-86]
@router.get("/users", response_model=ApiResponse[UserListResponse])
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserListResponse]:
    # ... implementation ...
```

### Frozen Dataclass Config (existing pattern)
```python
# Source: [VERIFIED: stockvaluefinder/config.py]
@dataclass(frozen=True)
class AuthConfig:
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
```

### ORM Model with UUID PK (existing pattern)
```python
# Source: [VERIFIED: stockvaluefinder/db/models/user_stock_access.py]
class UserStockAccessDB(Base):
    __tablename__ = "user_stock_access"
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String, sa.ForeignKey("users.id"), nullable=False, index=True
    )
```

### Lifespan Initialization (existing pattern)
```python
# Source: [VERIFIED: stockvaluefinder/main.py lines 43-93]
@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = init_cache(redis_url=settings.external_data.REDIS_URL)
    await cache.connect()
    init_rate_limiter(cache.redis)
    # NEW: init_usage_tracker(cache.redis), spawn flush background task
    yield
    # NEW: cancel flush background task
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-route tracking decorators | HTTP middleware + dependency hybrid | Standard FastAPI pattern | Centralized, no manual wiring per route |
| KEYS command for pattern matching | SCAN iterator | Redis best practice | Non-blocking key discovery |
| In-memory rate limit config | Redis Hash overrides + DB persistence | This phase (RATE-04) | Survives restart, shareable across workers |
| Synchronous flush via cron | asyncio background task in lifespan | Modern Python async | No external scheduler needed |

**Deprecated/outdated:**
- `redis.StrictRedis`: Use `redis.asyncio.Redis` (already in project)
- `@app.on_event("startup")`: Deprecated; use lifespan context manager (already in project)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `api_usage_records` table should use composite key (user_id, endpoint, period_start) for upsert dedup | Architecture Patterns | If wrong, duplicate rows; fixable with migration |
| A2 | Per-user rate limit overrides should be stored in both Redis (for fast lookup) and DB (for persistence) | Pattern 4 | If wrong, overrides lost on Redis restart; could be DB-only with cache |
| A3 | Background flush interval of 300 seconds (5 minutes) is appropriate for this scale | Pattern 3 | If wrong, Redis memory grows too fast or DB write frequency is too high |
| A4 | Middleware can reliably extract user identity from request.state if a dependency sets it before the route handler | Pattern 2 | If wrong, need to decode JWT in middleware (duplicates auth logic) |

## Open Questions

1. **Middleware user identity extraction strategy**
   - What we know: FastAPI middleware runs before dependencies, so `get_current_user` has not resolved yet
   - What's unclear: Whether to (a) decode JWT in middleware directly, (b) use a dependency that sets `request.state.user_id` before route handler, or (c) use a post-route middleware that reads user info from response context
   - Recommendation: Use approach (b) -- a `track_usage` dependency added to all protected routes that sets `request.state.user_id`. The middleware reads this after `call_next`. This avoids duplicating JWT decode logic and follows the existing pattern of using dependencies for cross-cutting concerns.

2. **Flush strategy: RENAME vs Lua script vs simple GET+DELETE**
   - What we know: Simple GET+DELETE has a race window where counts can be lost
   - What's unclear: Whether RENAME is safe when the target key might exist from a previous failed flush
   - Recommendation: Use RENAME to a flush-prefixed key, then HGETALL + DELETE. If flush-prefixed key exists, merge counts before processing. Simpler than a Lua script and sufficient for this scale.

3. **Error rate tracking granularity**
   - What we know: ANLY-04 requires "error rates" in aggregate stats
   - What's unclear: Whether to track per-endpoint errors or just total errors per user
   - Recommendation: Track per-endpoint errors in Redis Hash (field `errors:{endpoint}`), flush to DB with the same granularity. This enables per-endpoint error rate reporting.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | UsageTracker, RateLimiter overrides | Redis CLI not found locally, but CacheManager uses port 6380 | 7.2.1 (lib) | N/A (must have Redis running) |
| PostgreSQL | ApiUsageRecord persistence, queries | asyncpg 0.31.0 installed | -- | N/A |
| Python 3.12+ | Runtime | -- | 3.12 | -- |
| uv | Package management | Yes | 0.7.16 | -- |
| pytest | Testing | Yes | 9.0.2 | -- |

**Missing dependencies with no fallback:**
- None -- all required packages are already in pyproject.toml and installed in venv

**Missing dependencies with fallback:**
- Redis server must be running for integration tests; unit tests can mock Redis

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | pyproject.toml (tool.pytest.ini_options not present -- uses defaults) |
| Quick run command | `uv run pytest tests/unit/test_api/test_usage_tracker.py -x` |
| Full suite command | `uv run pytest tests/ -x --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANLY-01 | Track call count per user per endpoint | unit | `uv run pytest tests/unit/test_api/test_usage_tracker.py::test_record_request_increments_endpoint_counter -x` | Wave 0 |
| ANLY-02 | Track last active timestamp per user | unit | `uv run pytest tests/unit/test_api/test_usage_tracker.py::test_record_request_updates_last_active -x` | Wave 0 |
| ANLY-03 | Admin view per-user usage summary | integration | `uv run pytest tests/unit/test_api/test_analytics_routes.py::test_get_user_usage_summary -x` | Wave 0 |
| ANLY-04 | Admin view aggregate stats | integration | `uv run pytest tests/unit/test_api/test_analytics_routes.py::test_get_aggregate_stats -x` | Wave 0 |
| ANLY-05 | Periodic DB flush from Redis | unit | `uv run pytest tests/unit/test_api/test_usage_flush_service.py::test_flush_redis_to_db -x` | Wave 0 |
| RATE-04 | Admin adjust per-user rate limits | integration | `uv run pytest tests/unit/test_api/test_analytics_routes.py::test_set_user_rate_limit_override -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_api/test_usage_tracker.py tests/unit/test_api/test_analytics_routes.py -x`
- **Per wave merge:** `uv run pytest tests/ -x --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_api/test_usage_tracker.py` -- covers ANLY-01, ANLY-02
- [ ] `tests/unit/test_api/test_usage_flush_service.py` -- covers ANLY-05
- [ ] `tests/unit/test_api/test_analytics_routes.py` -- covers ANLY-03, ANLY-04, RATE-04
- [ ] `tests/unit/test_api/test_rate_limiter_override.py` -- covers RATE-04 unit tests for extended RateLimiter

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT via get_current_user dependency (existing) |
| V3 Session Management | yes | JWT tokens managed by JWTService (existing) |
| V4 Access Control | yes | require_admin dependency for all analytics endpoints (existing pattern) |
| V5 Input Validation | yes | Pydantic BaseModel validation for all request schemas |
| V6 Cryptography | no | No new cryptographic operations |

### Known Threat Patterns for FastAPI + Redis Analytics

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Admin endpoint unauthorized access | Elevation of Privilege | require_admin dependency (existing, verified) |
| Usage data injection (fake counts) | Tampering | Only middleware writes counters; admin endpoints are read-only |
| Rate limit override abuse | Elevation of Privilege | Only admin can set overrides; require_admin dependency |
| Redis key injection | Tampering | User_id from JWT (not user input); endpoint from request.url.path (server-side) |
| Analytics data exposure | Information Disclosure | Admin-only endpoints; no PII beyond user_id and call counts |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `middleware/rate_limiter.py` -- Redis INCR + EXPIRE pattern, RateLimitResult frozen dataclass
- Codebase analysis: `api/dependencies.py` -- get_current_user, require_admin, rate_limit dependency, init_rate_limiter
- Codebase analysis: `api/admin_routes.py` -- Admin endpoint pattern with require_admin, ApiResponse envelope
- Codebase analysis: `main.py` -- Lifespan initialization, middleware pattern, router inclusion
- Codebase analysis: `repositories/base.py` -- BaseRepository generic pattern
- Codebase analysis: `db/models/user.py`, `db/models/user_stock_access.py` -- ORM model patterns with UUID PK
- Codebase analysis: `models/api.py` -- ApiResponse[T] generic, PaginationMeta frozen
- Codebase analysis: `utils/cache.py` -- CacheManager with Redis pipeline, scan_iter, connect/disconnect
- Codebase analysis: `config.py` -- frozen dataclass config pattern, AuthConfig

### Secondary (MEDIUM confidence)
- FastAPI middleware documentation -- HTTP middleware pattern, request.state for inter-layer communication [ASSUMED]
- Redis Hash commands -- HINCRBY atomicity, HGETALL for bulk read [ASSUMED]
- asyncio.create_task for fire-and-forget background tasks [ASSUMED]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages already in project, verified versions from venv
- Architecture: HIGH - patterns directly derived from existing codebase (RateLimiter, CacheManager, admin routes, lifespan)
- Pitfalls: MEDIUM - middleware user identity extraction is a known FastAPI challenge; solution needs validation
- Testing: HIGH - existing test infrastructure with pytest, pytest-asyncio, and mock patterns

**Research date:** 2026-05-11
**Valid until:** 2026-06-11 (stable patterns, no fast-moving dependencies)
