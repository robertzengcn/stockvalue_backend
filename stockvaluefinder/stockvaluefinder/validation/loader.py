"""Singleton loader for the metric registry.

Uses ``functools.lru_cache`` to return the same frozen ``MetricRegistry``
instance on every call.  The YAML file is loaded from the package directory
using ``Path(__file__).parent`` so it works regardless of the current working
directory.

Usage::

    from stockvaluefinder.validation.loader import load_metric_registry

    registry = load_metric_registry()
    result = registry.check("m_score", -2.5, -2.52)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from stockvaluefinder.validation.schema import MetricRegistry


@lru_cache(maxsize=1)
def load_metric_registry() -> MetricRegistry:
    """Load and validate the metric registry from YAML.

    Returns a cached ``MetricRegistry`` singleton.  The YAML file is read
    from the package directory (``stockvaluefinder/validation/metric_registry.yaml``)
    and validated through the Pydantic schema on first call.

    Returns:
        Validated ``MetricRegistry`` instance.

    Raises:
        FileNotFoundError: If ``metric_registry.yaml`` is missing.
        pydantic.ValidationError: If YAML content fails schema validation.
    """
    yaml_path = Path(__file__).parent / "metric_registry.yaml"
    yaml_content = yaml_path.read_text(encoding="utf-8")
    return MetricRegistry.from_yaml(yaml_content)
