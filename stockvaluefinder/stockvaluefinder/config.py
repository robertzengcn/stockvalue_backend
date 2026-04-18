"""Application configuration settings.

This module contains all configuration constants used throughout the application.
Environment variables should be used for deployment-specific settings.
"""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ValuationConfig:
    """Configuration for DCF valuation calculations."""

    # Default beta (systematic risk)
    DEFAULT_BETA: float = 1.0

    # Default market risk premium (ERP)
    DEFAULT_MARKET_RISK_PREMIUM: float = 0.06  # 6%

    # Terminal growth rate range
    MIN_TERMINAL_GROWTH: float = -0.05  # -5%
    MAX_TERMINAL_GROWTH: float = 0.10  # 10%

    # Growth rate ranges
    MIN_GROWTH_RATE_STAGE1: float = -0.50  # -50%
    MAX_GROWTH_RATE_STAGE1: float = 1.0  # 100%
    MIN_GROWTH_RATE_STAGE2: float = -0.10  # -10%
    MAX_GROWTH_RATE_STAGE2: float = 0.50  # 50%

    # Stage duration
    MIN_YEARS_STAGE1: int = 1
    MAX_YEARS_STAGE1: int = 20
    MIN_YEARS_STAGE2: int = 0
    MAX_YEARS_STAGE2: int = 20

    # Valuation level thresholds (margin of safety)
    UNDERVALUED_THRESHOLD: float = 0.30  # 30%
    OVERVALUED_THRESHOLD: float = -0.30  # -30%


@dataclass(frozen=True)
class RiskConfig:
    """Configuration for risk analysis."""

    # Beneish M-Score threshold for manipulation
    BENEISH_M_SCORE_THRESHOLD: float = -1.78

    # Goodwill ratio threshold (goodwill / total assets)
    GOODWILL_RATIO_THRESHOLD: float = 0.30  # 30%

    # Profit vs cash flow divergence threshold
    PROFIT_CASH_DIVERGENCE_THRESHOLD: float = 0.20  # 20%


@dataclass(frozen=True)
class YieldConfig:
    """Configuration for yield gap analysis."""

    # Tax rates for dividend income
    HK_STOCK_CONNECT_TAX_RATE: float = 0.20  # 20% for HK shares via Stock Connect
    A_SHARE_TAX_RATE: float = 0.0  # 0% for A-shares (tax withheld by company)

    # Yield gap threshold for attractiveness
    YIELD_GAP_THRESHOLD: float = 0.0  # Positive yield gap = attractive


@dataclass(frozen=True)
class ExternalDataConfig:
    """Configuration for external data fetching."""

    # Data source priorities
    ENABLE_AKSHARE: bool = True

    # Redis connection URL
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cache durations (in seconds)
    PRICE_CACHE_TTL: int = 300  # 5 minutes (market hours)
    FINANCIAL_DATA_CACHE_TTL: int = 86400  # 24 hours (quarterly data)
    RATE_CACHE_TTL: int = 3600  # 1 hour (daily updates)
    SHARES_CACHE_TTL: int = 86400  # 24 hours (quarterly)
    DIVIDEND_CACHE_TTL: int = 86400  # 24 hours (TTM from history)
    FCF_CACHE_TTL: int = 86400  # 24 hours (quarterly)

    # Cache key versioning for invalidation control
    CACHE_KEY_VERSION: str = "v1"

    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0  # seconds


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for database connections."""

    # Connection pool settings
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10

    # Query timeout
    QUERY_TIMEOUT: int = 30  # seconds


@dataclass(frozen=True)
class RAGConfig:
    """Configuration for RAG pipeline (PDF processing, embeddings, vector search)."""

    # Qdrant connection
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "annual_reports"
    QDRANT_API_KEY: str | None = None

    # Embedding (OpenRouter bge-m3)
    EMBEDDING_API_URL: str = "https://openrouter.ai/api/v1/embeddings"
    EMBEDDING_API_KEY_ENV: str = "OPENROUTER_API_KEY"
    EMBEDDING_MODEL: str = "baai/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32

    # Chunking (parent-child document strategy)
    CHILD_CHUNK_TOKENS: int = 500
    PARENT_CHUNK_TOKENS: int = 2000
    CHUNK_OVERLAP_TOKENS: int = 50

    # Search
    SEARCH_SCORE_THRESHOLD: float = 0.7
    SEARCH_RESULT_LIMIT: int = 10
    MULTI_QUERY_COUNT: int = 3

    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100


@dataclass(frozen=True)
class AppConfig:
    """Overall application configuration."""

    valuation: ValuationConfig
    risk: RiskConfig
    yield_config: YieldConfig
    external_data: ExternalDataConfig
    database: DatabaseConfig

    @classmethod
    @lru_cache
    def get_instance(cls) -> "AppConfig":
        """Get singleton instance of application configuration.

        Returns:
            AppConfig instance with default settings
        """
        return cls(
            valuation=ValuationConfig(),
            risk=RiskConfig(),
            yield_config=YieldConfig(),
            external_data=ExternalDataConfig(),
            database=DatabaseConfig(),
        )


# Global configuration instances
settings = AppConfig.get_instance()
rag_config = RAGConfig()


__all__ = [
    "AppConfig",
    "ValuationConfig",
    "RiskConfig",
    "YieldConfig",
    "ExternalDataConfig",
    "DatabaseConfig",
    "RAGConfig",
    "settings",
    "rag_config",
]
