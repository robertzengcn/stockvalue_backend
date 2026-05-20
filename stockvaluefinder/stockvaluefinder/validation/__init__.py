"""Metric registry validation package.

Public API:
    Tolerance, InputField, ReferenceValue, Variant,
    MetricDefinition, MetricRegistry,
    load_metric_registry, ComparisonResult, compare_within_tolerance
"""

from stockvaluefinder.validation.comparators import (
    ComparisonResult,
    compare_within_tolerance,
)
from stockvaluefinder.validation.loader import load_metric_registry
from stockvaluefinder.validation.schema import (
    InputField,
    MetricDefinition,
    MetricRegistry,
    ReferenceValue,
    Tolerance,
    Variant,
)

__all__ = [
    "Tolerance",
    "InputField",
    "ReferenceValue",
    "Variant",
    "MetricDefinition",
    "MetricRegistry",
    "load_metric_registry",
    "ComparisonResult",
    "compare_within_tolerance",
]
