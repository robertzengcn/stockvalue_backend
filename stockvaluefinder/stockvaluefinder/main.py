"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env before imports that read os.environ at module level (e.g. db.base).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from arq import create_pool  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from stockvaluefinder.api.risk_routes import router as risk_router  # noqa: E402
from stockvaluefinder.api.valuation_routes import router as valuation_router  # noqa: E402
from stockvaluefinder.api.yield_routes import router as yield_router  # noqa: E402
from stockvaluefinder.api.documents_routes import router as documents_router  # noqa: E402
from stockvaluefinder.api.pipeline_routes import router as pipeline_router  # noqa: E402
from stockvaluefinder.api.roic_routes import router as roic_router  # noqa: E402
from stockvaluefinder.api.capex_routes import router as capex_router  # noqa: E402
from stockvaluefinder.api.policy_routes import router as policy_router  # noqa: E402
from stockvaluefinder.api.alpha_routes import router as alpha_router  # noqa: E402
from stockvaluefinder.api.auth_routes import router as auth_router  # noqa: E402
from stockvaluefinder.api.admin_routes import router as admin_router
from stockvaluefinder.api.scanner_routes import router as scanner_router  # noqa: E402
from stockvaluefinder.api.analytics_routes import router as analytics_router  # noqa: E402
from stockvaluefinder.api.dependencies import (  # noqa: E402
    check_qdrant_health,
    init_cache,
    init_rate_limiter,
    init_token_blacklist,
    init_usage_tracker,
)
from stockvaluefinder.middleware.usage_middleware import (  # noqa: E402
    usage_tracking_middleware as _usage_tracking_middleware,
)
from stockvaluefinder.config import get_arq_redis_settings, settings  # noqa: E402
from stockvaluefinder.models.valuation import _rebuild_forward_refs  # noqa: E402
from stockvaluefinder.services.usage_flush_service import UsageFlushService  # noqa: E402
from stockvaluefinder.utils.errors import StockValueFinderError  # noqa: E402
from stockvaluefinder.utils.logging import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)

# Module-level background task handle for usage flush loop
_flush_task: asyncio.Task | None = None


async def _usage_flush_loop(
    redis,
    session_factory,
    interval_seconds: int = 300,
) -> None:
    """Background loop that periodically flushes Redis usage data to PostgreSQL.

    Args:
        redis: Connected Redis async client
        session_factory: Async session factory for DB access
        interval_seconds: Seconds between flush cycles (default 300 = 5 min)
    """
    flush_service = UsageFlushService(redis=redis, session_factory=session_factory)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            count = await flush_service.flush_redis_to_db()
            logger.info(f"Usage flush completed: {count} records written")
        except Exception as e:
            logger.warning(f"Usage flush failed: {e}")


# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Initializes Redis cache on startup with graceful degradation if
    Redis is unavailable. Disconnects cache on shutdown.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup: Initialize Redis cache
    cache = init_cache(redis_url=settings.external_data.REDIS_URL)
    try:
        await cache.connect()
        app.state.cache = cache
        logger.info("Redis cache initialized successfully")

        # Initialize rate limiter using the connected Redis client
        init_rate_limiter(cache.redis)
        logger.info("Rate limiter initialized (100 requests/hour per user)")

        # Initialize token blacklist for logout/rotation
        init_token_blacklist(cache.redis)
        logger.info("Token blacklist initialized")

        # Initialize usage tracker using the connected Redis client
        init_usage_tracker(cache.redis)
        logger.info("Usage tracker initialized")

        # Spawn background flush task for Redis -> DB usage persistence
        from stockvaluefinder.db.base import async_session_maker

        global _flush_task
        _flush_task = asyncio.create_task(
            _usage_flush_loop(cache.redis, async_session_maker)
        )
        logger.info("Usage flush background task started (interval: 300s)")
    except Exception as e:
        logger.warning(f"Redis cache unavailable, continuing without cache: {e}")
        app.state.cache = None

    # Startup: Check Qdrant health (graceful degradation if unavailable)
    try:
        qdrant_ok = check_qdrant_health()
        if qdrant_ok:
            logger.info("Qdrant vector store initialized successfully")
        else:
            logger.warning(
                "Qdrant vector store unavailable, "
                "document upload and search will not work"
            )
    except Exception as e:
        logger.warning(f"Qdrant health check failed, continuing without Qdrant: {e}")

    # Startup: Initialize Arq connection pool (for enqueuing from FastAPI)
    arq_pool = None
    try:
        arq_pool = await create_pool(get_arq_redis_settings())
        app.state.arq_pool = arq_pool
        logger.info("Arq pool initialized successfully")
    except Exception as e:
        logger.warning(f"Arq pool unavailable, pipeline enqueuing disabled: {e}")
        app.state.arq_pool = None

    yield

    # Shutdown: Cancel usage flush background task
    if _flush_task is not None:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None
        logger.info("Usage flush background task cancelled")

    # Shutdown: Close Arq pool
    if arq_pool is not None:
        try:
            await arq_pool.close()
            logger.info("Arq pool closed")
        except Exception as e:
            logger.warning(f"Error closing Arq pool: {e}")

    # Shutdown: Disconnect cache
    if app.state.cache is not None:
        try:
            await app.state.cache.disconnect()
            logger.info("Redis cache disconnected")
        except Exception as e:
            logger.warning(f"Error disconnecting Redis cache: {e}")


# Create FastAPI application
app = FastAPI(
    title="StockValueFinder API",
    description="AI-enhanced value investment decision platform for A-share and Hong Kong stocks",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend (e.g. Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(StockValueFinderError)
async def stockvaluefinder_error_handler(request, exc: StockValueFinderError):
    """Handle custom application errors.

    Args:
        request: FastAPI request
        exc: StockValueFinderError exception

    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "data": None,
            "error": exc.message,
            "meta": {"details": exc.details} if exc.details else None,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "stockvaluefinder", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "StockValueFinder API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.middleware("http")
async def usage_tracking_middleware(request, call_next):
    """Track API usage for authenticated requests under /api/v1/."""
    return await _usage_tracking_middleware(request, call_next)


@app.middleware("http")
async def rate_limit_headers_middleware(request, call_next):
    """Add rate limit headers to responses when available."""
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_result"):
        result = request.state.rate_limit_result
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
    return response


app.include_router(risk_router)
app.include_router(yield_router)
app.include_router(valuation_router)
app.include_router(documents_router)
app.include_router(pipeline_router)
app.include_router(roic_router)
app.include_router(capex_router)
app.include_router(policy_router)
app.include_router(alpha_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(scanner_router)

# Resolve forward references after all modules are imported
_rebuild_forward_refs()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("stockvaluefinder.main:app", host="0.0.0.0", port=8000, reload=True)
