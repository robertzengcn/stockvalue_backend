"""Pydantic V2 frozen models for the metric registry.

Defines the schema hierarchy that validates ``metric_registry.yaml`` at load
time.  All models are immutable (``frozen=True``) and use Python 3.12+ type
syntax.

Model hierarchy::

    MetricRegistry
      └─ MetricDefinition (one per metric entry)
           ├─ Tolerance
           ├─ InputField
           ├─ ReferenceValue
           └─ Variant (sector overrides)

Usage::

    from stockvaluefinder.validation.schema import MetricRegistry

    registry = MetricRegistry.from_yaml(yaml_string)
    metric = registry.get("m_score")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class Tolerance(BaseModel):
    """Validation tolerance for a metric.

    At least one of ``absolute`` or ``relative`` must be provided.

    Attributes:
        absolute: Absolute tolerance (e.g. 0.05 for M-Score).
        relative: Relative tolerance as fraction (e.g. 0.01 for 1%).
    """

    absolute: float | None = None
    relative: float | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _at_least_one(self) -> Tolerance:
        """Ensure at least one tolerance value is set."""
        if self.absolute is None and self.relative is None:
            msg = "Tolerance must have at least one of 'absolute' or 'relative'"
            raise ValueError(msg)
        return self


class InputField(BaseModel):
    """Parameter contract for a ``calculate_*`` function.

    Attributes:
        name: Parameter name as it appears in the function signature.
        type: Type annotation string (e.g. ``"float"``, ``"dict[str, Any]"``).
        akshare_field: Mapping to AKShare raw field name, if applicable.
        efinance_field: Mapping to efinance raw field name, if applicable.
        required: Whether the parameter is required (default True).
        description: Human-readable description of the parameter.
    """

    name: str
    type: str
    akshare_field: str | None = None
    efinance_field: str | None = None
    required: bool = True
    description: str | None = None

    model_config = {"frozen": True}


class ReferenceValue(BaseModel):
    """L1 test reference value from published paper or textbook.

    Attributes:
        name: Identifier for this reference case.
        inputs: Named input values for the test.
        expected_output: Expected result (scalar or dict of scalars).
        source: Academic citation (e.g. ``"Beneish 1999, Table 3"``).
    """

    name: str
    inputs: dict[str, float | str | bool]
    expected_output: float | dict[str, float]
    source: str | None = None

    model_config = {"frozen": True}


class Variant(BaseModel):
    """Sector-specific override for a metric definition.

    Overrides are merged into the base ``MetricDefinition`` when a caller
    requests a metric with a specific sector.

    Attributes:
        function: Override module path (e.g. ``"roic_service.calculate_nopat"``).
        params: Override parameter list.
        tolerance: Override tolerance.
        display_name_suffix: Suffix appended to display name (e.g. ``(Financial Sector)``).
    """

    function: str | None = None
    params: list[InputField] | None = None
    tolerance: Tolerance | None = None
    display_name_suffix: str | None = None

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class MetricDefinition(BaseModel):
    """Full definition of a single metric in the registry.

    Attributes:
        display_name: Human-readable name (e.g. ``"Beneish M-Score"``).
        category: Analysis module: risk, roic, valuation, yield, capex, policy, alpha.
        function: Dotted module path + function name.
        params: Function parameter contracts.
        returns: Return type description.
        tolerance: Validation tolerance for this metric.
        formula_ref: Academic paper or textbook citation.
        audit_trail_required: Whether the function produces an audit trail.
        depends_on: Names of upstream metrics this depends on.
        priority: Validation priority (P0, P1, P2).
        variants: Sector variants keyed by variant name.
        reference_values: L1 test reference values from papers.
        notes: Free-form implementation notes.
    """

    display_name: str
    category: str
    function: str
    params: list[InputField]
    returns: str
    tolerance: Tolerance
    formula_ref: str | None = None
    audit_trail_required: bool = False
    depends_on: list[str] = []
    priority: str = "P2"
    variants: dict[str, Variant] = {}
    reference_values: list[ReferenceValue] = []
    notes: str | None = None

    model_config = {"frozen": True}


class MetricRegistry(BaseModel):
    """Root model for the metric registry.

    Validates the full YAML structure at load time, including cross-reference
    checks on ``depends_on`` fields.

    Attributes:
        metrics: Flat dict of metric definitions keyed by metric name.
    """

    metrics: dict[str, MetricDefinition]

    model_config = {"frozen": True}

    # -- Cross-reference validation -----------------------------------------

    @model_validator(mode="after")
    def _validate_depends_on(self) -> MetricRegistry:
        """Check that all ``depends_on`` entries reference existing metrics."""
        all_names = set(self.metrics.keys())
        for name, metric in self.metrics.items():
            for dep in metric.depends_on:
                if dep not in all_names:
                    msg = (
                        f"Metric '{name}' depends_on '{dep}', "
                        f"which does not exist in the registry"
                    )
                    raise ValueError(msg)
        return self

    # -- Class methods -------------------------------------------------------

    @classmethod
    def from_yaml(cls, yaml_string: str) -> MetricRegistry:
        """Parse and validate a YAML string into a ``MetricRegistry``.

        Args:
            yaml_string: YAML content matching the registry schema.

        Returns:
            Validated ``MetricRegistry`` instance.

        Raises:
            ValueError: If the YAML is structurally invalid.
            pydantic.ValidationError: If schema validation fails.
        """
        raw: dict[str, Any] = yaml.safe_load(yaml_string)
        return cls.model_validate(raw)

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> MetricRegistry:
        """Load and validate a YAML file into a ``MetricRegistry``.

        Args:
            path: Path to the YAML file.

        Returns:
            Validated ``MetricRegistry`` instance.
        """
        content = Path(path).read_text(encoding="utf-8")
        return cls.from_yaml(content)

    # -- Convenience methods -------------------------------------------------

    def get(self, name: str, sector: str | None = None) -> MetricDefinition:
        """Retrieve a metric by name, optionally resolved to a sector variant.

        When ``sector`` is given and the metric has a matching variant, the
        variant overrides are applied to the base definition.

        Args:
            name: Metric name (e.g. ``"nopat"``).
            sector: Sector variant name (e.g. ``"financial"``), or None.

        Returns:
            ``MetricDefinition`` with variant overrides applied if applicable.

        Raises:
            KeyError: If the metric name is not found in the registry.
        """
        if name not in self.metrics:
            raise KeyError(f"Metric '{name}' not found in registry")

        metric = self.metrics[name]

        if sector is None or sector not in metric.variants:
            return metric

        variant = metric.variants[sector]

        # Build a merged definition using variant overrides
        merged_data = metric.model_dump()
        if variant.function is not None:
            merged_data["function"] = variant.function
        if variant.params is not None:
            merged_data["params"] = [p.model_dump() for p in variant.params]
        if variant.tolerance is not None:
            merged_data["tolerance"] = variant.tolerance.model_dump()
        if variant.display_name_suffix is not None:
            merged_data["display_name"] = (
                f"{metric.display_name} {variant.display_name_suffix}"
            )

        return MetricDefinition.model_validate(merged_data)

    def metrics_by_category(self, category: str) -> list[tuple[str, MetricDefinition]]:
        """Return all metrics matching the given category.

        Args:
            category: Category to filter by (e.g. ``"risk"``).

        Returns:
            List of ``(name, definition)`` tuples.
        """
        return [
            (name, metric)
            for name, metric in self.metrics.items()
            if metric.category == category
        ]

    def p0_metrics(self) -> list[tuple[str, MetricDefinition]]:
        """Return all P0-priority metrics.

        Returns:
            List of ``(name, definition)`` tuples where priority is ``"P0"``.
        """
        return [
            (name, metric)
            for name, metric in self.metrics.items()
            if metric.priority == "P0"
        ]

    def all_metrics(self) -> list[tuple[str, MetricDefinition]]:
        """Return all metrics as ``(name, definition)`` tuples.

        Returns:
            List of all metric entries.
        """
        return list(self.metrics.items())
