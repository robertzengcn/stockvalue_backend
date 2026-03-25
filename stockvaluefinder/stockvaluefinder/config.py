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

    # Cache duration (in seconds)
    PRICE_CACHE_TTL: int = 300  # 5 minutes
    FINANCIAL_DATA_CACHE_TTL: int = 86400  # 24 hours

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


# Global configuration instance
settings = AppConfig.get_instance()


__all__ = [
    "AppConfig",
    "ValuationConfig",
    "RiskConfig",
    "YieldConfig",
    "ExternalDataConfig",
    "DatabaseConfig",
    "settings",
]
