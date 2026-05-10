"""Application configuration settings.

This module contains all configuration constants used throughout the application.
Environment variables should be used for deployment-specific settings.
"""

import os
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
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6380/0")

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
class ROICConfig:
    """Configuration for ROIC-WACC spread analysis."""

    # Moat trend detection threshold (slope per year)
    MOAT_TREND_THRESHOLD: float = 0.005

    # Minimum valid data points for trend analysis
    MIN_TREND_DATA_POINTS: int = 3

    # Keywords identifying financial sector stocks (D-09)
    FINANCIAL_SECTOR_KEYWORDS: tuple[str, ...] = ("银行", "保险", "证券")

    # Default lookback years for multi-year trend
    MULTI_YEAR_LOOKBACK: int = 3

    # Default risk-free rate when treasury yield fetch fails
    DEFAULT_RISK_FREE_RATE: float = 0.025


@dataclass(frozen=True)
class CapitalAllocationConfig:
    """Configuration for capital allocation scorecard analysis."""

    # Blind expansion threshold: YoY CapEx growth > 20% triggers alert (D-05)
    CAPEX_GROWTH_THRESHOLD: float = 0.20

    # DPU trend detection threshold (slope per year) (D-04)
    DPU_TREND_THRESHOLD: float = 0.05

    # Minimum data points for DPU trend analysis
    MIN_DPU_DATA_POINTS: int = 3

    # Buyback yield grade boundaries (per dimension)
    BUYBACK_YIELD_GRADE_A: float = 0.02  # > 2%
    BUYBACK_YIELD_GRADE_B: float = 0.01  # 1-2%
    BUYBACK_YIELD_GRADE_C: float = 0.005  # 0.5-1%

    # Expansion discipline grade boundaries
    # No alert = A, alert + growth 20-50% = C, alert + growth > 50% = D
    EXPANSION_ALERT_GRADE_C_THRESHOLD: float = 0.50

    # Combined scorecard grade boundaries (numeric: A=4, B=3, C=2, D=1)
    OVERALL_GRADE_A_THRESHOLD: float = 3.5
    OVERALL_GRADE_B_THRESHOLD: float = 2.5
    OVERALL_GRADE_C_THRESHOLD: float = 1.5

    # Equal weights for three dimensions (D-08)
    DIMENSION_WEIGHTS: tuple[float, float, float] = (1.0 / 3, 1.0 / 3, 1.0 / 3)


@dataclass(frozen=True)
class PolicyResonanceConfig:
    """Configuration for policy resonance analysis (D-04 through D-08).

    Controls the scoring formula weights, tier thresholds, DCF adjustment
    percentages, and search parameters for policy-stock matching.
    """

    # Number of top policy chunks to match per stock (D-02)
    MATCH_LIMIT: int = 5

    # Scoring formula weights (D-04): 60% cosine, 40% LLM confidence
    COSINE_WEIGHT: float = 0.60
    LLM_WEIGHT: float = 0.40

    # Resonance threshold to qualify as policy-aligned (D-06)
    RESONANCE_THRESHOLD: float = 40.0

    # Strongly Supportive tier threshold (D-07)
    STRONG_TIER_THRESHOLD: float = 80.0

    # DCF terminal growth adjustments per tier (D-07)
    STRONG_ADJUSTMENT: float = 0.015  # +1.5%
    MODERATE_ADJUSTMENT: float = 0.01  # +1.0%
    NEUTRAL_ADJUSTMENT: float = 0.0  # 0%

    # Hard cap on terminal growth adjustment (D-08)
    MAX_ADJUSTMENT_CAP: float = 0.015

    # Vector search minimum score threshold
    VECTOR_SEARCH_THRESHOLD: float = 0.5

    # Cache TTL for stock business descriptions (24h)
    BUSINESS_DESC_CACHE_TTL: int = 86400


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
class AlphaConfig:
    """Configuration for Alpha composite score analysis.

    Fixed weights for aggregating four forward-looking analysis dimensions
    into a single 0-100 composite score.

    Weights: ROIC-WACC 40%, Capital Allocation 30%, Policy 20%, Moat 10%.
    """

    # Fixed weights per ROADMAP specification
    ROIC_WACC_WEIGHT: float = 0.40
    CAPITAL_ALLOCATION_WEIGHT: float = 0.30
    POLICY_WEIGHT: float = 0.20
    MOAT_WEIGHT: float = 0.10

    # ROIC-WACC spread normalization bounds (D-02)
    SPREAD_CLAMP_MIN: float = -0.10  # -10%
    SPREAD_CLAMP_MAX: float = 0.10  # +10%


@dataclass(frozen=True)
class AuthConfig:
    """Configuration for JWT authentication."""

    # JWT secret key (MUST be set via environment variable in production)
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")

    # JWT algorithm
    JWT_ALGORITHM: str = "HS256"

    # Access token expiry (15 minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Refresh token expiry (7 days)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Bcrypt rounds
    BCRYPT_ROUNDS: int = 12


@dataclass(frozen=True)
class AppConfig:
    """Overall application configuration."""

    valuation: ValuationConfig
    risk: RiskConfig
    yield_config: YieldConfig
    external_data: ExternalDataConfig
    database: DatabaseConfig
    roic: ROICConfig
    capital_allocation: CapitalAllocationConfig
    policy_resonance: PolicyResonanceConfig
    alpha: AlphaConfig
    auth: AuthConfig

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
            roic=ROICConfig(),
            capital_allocation=CapitalAllocationConfig(),
            policy_resonance=PolicyResonanceConfig(),
            alpha=AlphaConfig(),
            auth=AuthConfig(),
        )


# Global configuration instances
settings = AppConfig.get_instance()
rag_config = RAGConfig()
roic_config = ROICConfig()
capital_allocation_config = CapitalAllocationConfig()
policy_resonance_config = PolicyResonanceConfig()
alpha_config = AlphaConfig()
auth_config = AuthConfig()


__all__ = [
    "AppConfig",
    "AlphaConfig",
    "AuthConfig",
    "CapitalAllocationConfig",
    "PolicyResonanceConfig",
    "ValuationConfig",
    "RiskConfig",
    "YieldConfig",
    "ExternalDataConfig",
    "DatabaseConfig",
    "RAGConfig",
    "ROICConfig",
    "settings",
    "rag_config",
    "roic_config",
    "capital_allocation_config",
    "policy_resonance_config",
    "alpha_config",
    "auth_config",
]
