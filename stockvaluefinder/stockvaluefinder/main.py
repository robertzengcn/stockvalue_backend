"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from stockvaluefinder.api.risk_routes import router as risk_router
from stockvaluefinder.api.valuation_routes import router as valuation_router
from stockvaluefinder.api.yield_routes import router as yield_router
from stockvaluefinder.api.documents_routes import router as documents_router
from stockvaluefinder.api.pipeline_routes import router as pipeline_router
from stockvaluefinder.api.roic_routes import router as roic_router
from stockvaluefinder.api.dependencies import check_qdrant_health, init_cache
from stockvaluefinder.config import settings
from stockvaluefinder.models.valuation import _rebuild_forward_refs
from stockvaluefinder.utils.errors import StockValueFinderError
from stockvaluefinder.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

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
        arq_pool = await create_pool(RedisSettings())
        app.state.arq_pool = arq_pool
        logger.info("Arq pool initialized successfully")
    except Exception as e:
        logger.warning(f"Arq pool unavailable, pipeline enqueuing disabled: {e}")
        app.state.arq_pool = None

    yield

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


app.include_router(risk_router)
app.include_router(yield_router)
app.include_router(valuation_router)
app.include_router(documents_router)
app.include_router(pipeline_router)
app.include_router(roic_router)

# Resolve forward references after all modules are imported
_rebuild_forward_refs()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("stockvaluefinder.main:app", host="0.0.0.0", port=8000, reload=True)
