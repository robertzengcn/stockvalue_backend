"""Market Index Value Scanner package.

This package implements a systematic scanner that discovers undervalued
stocks across CSI 300 and CSI 500 index pools using a 3-layer screening
funnel: market coarse screen, value confirmation, quality/risk review.
"""

from stockvaluefinder.market_scanner.config import (
    MarketScannerConfig,
    ScoringWeightsConfig,
)
from stockvaluefinder.market_scanner.models import (
    CandidateReasons,
    CompositeScore,
    CompositeScoreComponents,
    ScreeningResult,
    ScreeningSnapshot,
)

__all__ = [
    "CandidateReasons",
    "CompositeScore",
    "CompositeScoreComponents",
    "MarketScannerConfig",
    "ScreeningResult",
    "ScreeningSnapshot",
    "ScoringWeightsConfig",
]
