"""Validate metric_registry.yaml against the Pydantic schema.

Exits 0 if valid, 1 if invalid.  Prints validation summary to stdout.
Designed for use as a pre-commit hook and CI early-check step.

Usage::

    uv run python -m stockvaluefinder.tools.validate_registry
    uv run python stockvaluefinder/tools/validate_registry.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from stockvaluefinder.validation.schema import MetricRegistry


def _registry_path() -> Path:
    """Resolve the metric_registry.yaml path relative to this script."""
    return Path(__file__).parent.parent / "validation" / "metric_registry.yaml"


def validate_registry(yaml_path: Path | None = None) -> MetricRegistry:
    """Load and validate the metric registry YAML.

    Args:
        yaml_path: Optional explicit path.  Defaults to the package
            ``validation/metric_registry.yaml``.

    Returns:
        Validated ``MetricRegistry`` instance.

    Raises:
        SystemExit: On validation failure (exit code 1).
    """
    path = yaml_path or _registry_path()

    if not path.exists():
        print(f"ERROR: Registry file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        registry = MetricRegistry.from_yaml_file(path)
    except ValidationError as exc:
        print("ERROR: metric_registry.yaml failed schema validation:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    return registry


def _print_summary(registry: MetricRegistry) -> None:
    """Print a human-readable validation summary."""
    metrics = registry.metrics
    total = len(metrics)

    categories = Counter(m.category for m in metrics.values())
    priorities = Counter(m.priority for m in metrics.values())

    print(f"Registry valid: {total} metrics")
    print(
        "  Categories: "
        + ", ".join(f"{cat}={cnt}" for cat, cnt in sorted(categories.items()))
    )
    print(
        "  Priorities: "
        + ", ".join(f"{pri}={cnt}" for pri, cnt in sorted(priorities.items()))
    )


def main() -> None:
    """Entry point for the validation script."""
    registry = validate_registry()
    _print_summary(registry)


if __name__ == "__main__":
    main()
