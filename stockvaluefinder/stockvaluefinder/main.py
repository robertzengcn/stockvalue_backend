"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from stockvaluefinder.api.risk_routes import router as risk_router
from stockvaluefinder.api.valuation_routes import router as valuation_router
from stockvaluefinder.api.yield_routes import router as yield_router
from stockvaluefinder.utils.errors import StockValueFinderError
from stockvaluefinder.utils.logging import setup_logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Yields:
        None
    """
    # Startup
    # TODO: Initialize database connection
    # TODO: Initialize Redis cache
    # TODO: Initialize Qdrant client
    yield
    # Shutdown
    # TODO: Close database connections
    # TODO: Close cache connections


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("stockvaluefinder.main:app", host="0.0.0.0", port=8000, reload=True)
