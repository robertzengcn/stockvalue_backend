"""Pipeline module for automated financial report processing.

This module provides the infrastructure for downloading, parsing,
and analyzing A-share financial reports through an event-driven pipeline.
"""

from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.models import (
    HealthStatus,
    PipelineDocumentCreate,
    PipelineTaskCreate,
)
from stockvaluefinder.pipeline.state import (
    PipelineState,
    VALID_TRANSITIONS,
    validate_transition,
)

__all__ = [
    "HealthStatus",
    "PipelineConfig",
    "PipelineDocumentCreate",
    "PipelineState",
    "PipelineTaskCreate",
    "VALID_TRANSITIONS",
    "validate_transition",
]
