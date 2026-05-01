"""Pipeline module for automated financial report processing.

This module provides the infrastructure for downloading, parsing,
and analyzing A-share financial reports through an event-driven pipeline.
"""

from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.models import (
    HealthStatus,
    PendingDisclosureCreate,
    PipelineDocumentCreate,
    PipelineTaskCreate,
    WatcherStateUpdate,
    WatchlistItemCreate,
    WatchlistItemResponse,
)
from stockvaluefinder.pipeline.state import (
    PipelineState,
    VALID_TRANSITIONS,
    validate_transition,
)

__all__ = [
    "HealthStatus",
    "PendingDisclosureCreate",
    "PipelineConfig",
    "PipelineDocumentCreate",
    "PipelineState",
    "PipelineTaskCreate",
    "VALID_TRANSITIONS",
    "WatcherStateUpdate",
    "WatchlistItemCreate",
    "WatchlistItemResponse",
    "validate_transition",
]
