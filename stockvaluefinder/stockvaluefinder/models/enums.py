"""Enumeration types for StockValueFinder domain models."""

from enum import Enum


class Market(str, Enum):
    """Stock market classification."""

    A_SHARE = "A_SHARE"  # A-shares (Shanghai/Shenzhen)
    HK_SHARE = "HK_SHARE"  # Hong Kong stocks


class ReportType(str, Enum):
    """Financial report type."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"


class RiskLevel(str, Enum):
    """Risk assessment level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DividendFrequency(str, Enum):
    """Dividend payment frequency."""

    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    SPECIAL = "SPECIAL"


class Currency(str, Enum):
    """Currency type."""

    CNY = "CNY"
    HKD = "HKD"


class YieldRecommendation(str, Enum):
    """Investment recommendation based on yield gap analysis."""

    ATTRACTIVE = "ATTRACTIVE"
    NEUTRAL = "NEUTRAL"
    UNATTRACTIVE = "UNATTRACTIVE"


class ValuationLevel(str, Enum):
    """Valuation assessment level."""

    SIGNIFICANTLY_UNDERVALUED = "SIGNIFICANTLY_UNDERVALUED"
    UNDERVALUED = "UNDERVALUED"
    FAIR_VALUE = "FAIR_VALUE"
    OVERVALUED = "OVERVALUED"
    SIGNIFICANTLY_OVERVALUED = "SIGNIFICANTLY_OVERVALUED"


class ResonanceTier(str, Enum):
    """Policy resonance tier classification (D-07)."""

    STRONGLY_SUPPORTIVE = "strongly_supportive"
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"


class AlphaLevel(str, Enum):
    """Composite Alpha score classification level."""

    EXCELLENT = "EXCELLENT"  # >= 80
    GOOD = "GOOD"  # >= 60
    FAIR = "FAIR"  # >= 40
    WEAK = "WEAK"  # >= 20
    POOR = "POOR"  # < 20
