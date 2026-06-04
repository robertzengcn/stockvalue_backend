"""Tests for metric registry Pydantic schema models.

Covers:
- Schema validation of well-formed metric entries
- Rejection of entries with missing required fields
- Sector variant parsing and override
- depends_on cross-reference validation
- Frozen model enforcement
- Tolerance model constraints
- YAML loading via from_yaml()
- ReferenceValue and InputField models
"""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from stockvaluefinder.validation.schema import (
    InputField,
    MetricRegistry,
    ReferenceValue,
    Tolerance,
    Variant,
)


# ---------------------------------------------------------------------------
# Minimal valid helpers
# ---------------------------------------------------------------------------


def _minimal_entry(**overrides) -> dict:
    """Return a minimal valid metric entry dict, with optional overrides."""
    entry = {
        "display_name": "Test Metric",
        "category": "risk",
        "function": "risk_service.calculate_test",
        "params": [
            {"name": "x", "type": "float"},
        ],
        "returns": "float",
        "tolerance": {"absolute": 0.01},
    }
    entry.update(overrides)
    return entry


def _minimal_registry(metrics: dict[str, dict] | None = None) -> dict:
    """Return a minimal valid registry dict."""
    if metrics is None:
        metrics = {"test_metric": _minimal_entry()}
    return {"metrics": metrics}


# ---------------------------------------------------------------------------
# Test 1: Valid registry succeeds
# ---------------------------------------------------------------------------


class TestValidRegistry:
    """MetricRegistry.model_validate succeeds with all required fields."""

    def test_valid_full_registry(self) -> None:
        registry = MetricRegistry.model_validate(
            _minimal_registry(
                metrics={
                    "dsri": _minimal_entry(
                        display_name="DSRI",
                        function="risk_service.calculate_mscore_indices",
                        depends_on=[],
                        priority="P0",
                    ),
                    "gmi": _minimal_entry(
                        display_name="GMI",
                        function="risk_service.calculate_mscore_indices",
                        depends_on=[],
                    ),
                }
            )
        )
        assert len(registry.metrics) == 2
        assert "dsri" in registry.metrics
        assert registry.metrics["dsri"].display_name == "DSRI"

    def test_valid_minimal_entry(self) -> None:
        registry = MetricRegistry.model_validate(_minimal_registry())
        metric = registry.metrics["test_metric"]
        assert metric.display_name == "Test Metric"
        assert metric.category == "risk"
        assert metric.function == "risk_service.calculate_test"
        assert len(metric.params) == 1
        assert metric.params[0].name == "x"
        assert metric.tolerance.absolute == 0.01
        assert metric.tolerance.relative is None
        assert metric.returns == "float"


# ---------------------------------------------------------------------------
# Tests 2-5: Missing required fields
# ---------------------------------------------------------------------------


class TestMissingRequiredFields:
    """Schema rejects YAML with missing required fields."""

    def test_missing_display_name(self) -> None:
        entry = _minimal_entry()
        del entry["display_name"]
        with pytest.raises(ValidationError, match="display_name"):
            MetricRegistry.model_validate(_minimal_registry(metrics={"bad": entry}))

    def test_missing_tolerance(self) -> None:
        entry = _minimal_entry()
        del entry["tolerance"]
        with pytest.raises(ValidationError, match="tolerance"):
            MetricRegistry.model_validate(_minimal_registry(metrics={"bad": entry}))

    def test_missing_category(self) -> None:
        entry = _minimal_entry()
        del entry["category"]
        with pytest.raises(ValidationError, match="category"):
            MetricRegistry.model_validate(_minimal_registry(metrics={"bad": entry}))

    def test_missing_function(self) -> None:
        entry = _minimal_entry()
        del entry["function"]
        with pytest.raises(ValidationError, match="function"):
            MetricRegistry.model_validate(_minimal_registry(metrics={"bad": entry}))


# ---------------------------------------------------------------------------
# Test 6: Sector variants
# ---------------------------------------------------------------------------


class TestSectorVariants:
    """Entry with variants correctly parses overrides."""

    def test_variants_override_function_params_tolerance(self) -> None:
        entry = _minimal_entry(
            variants={
                "financial": {
                    "function": "roic_service.calculate_nopat_financial",
                    "params": [
                        {"name": "profit_data", "type": "dict[str, Any]"},
                        {"name": "is_financial", "type": "bool"},
                    ],
                    "tolerance": {"relative": 0.02},
                    "display_name_suffix": "(Financial Sector)",
                },
                "non_financial": {
                    "function": "roic_service.calculate_nopat_non_financial",
                    "params": [
                        {"name": "profit_data", "type": "dict[str, Any]"},
                        {"name": "is_financial", "type": "bool"},
                    ],
                    "tolerance": {"relative": 0.03},
                },
            }
        )
        registry = MetricRegistry.model_validate(
            _minimal_registry(metrics={"nopat": entry})
        )
        metric = registry.metrics["nopat"]
        assert "financial" in metric.variants
        assert (
            metric.variants["financial"].function
            == "roic_service.calculate_nopat_financial"
        )
        assert metric.variants["financial"].tolerance is not None
        assert metric.variants["financial"].tolerance.relative == 0.02  # type: ignore[union-attr]
        assert metric.variants["financial"].display_name_suffix == "(Financial Sector)"
        assert "non_financial" in metric.variants
        assert (
            metric.variants["non_financial"].function
            == "roic_service.calculate_nopat_non_financial"
        )


# ---------------------------------------------------------------------------
# Test 7: depends_on cross-reference validation
# ---------------------------------------------------------------------------


class TestDependsOnValidation:
    """depends_on entries must reference existing metric names."""

    def test_valid_depends_on(self) -> None:
        registry = MetricRegistry.model_validate(
            _minimal_registry(
                metrics={
                    "dsri": _minimal_entry(display_name="DSRI"),
                    "m_score": _minimal_entry(
                        display_name="M-Score",
                        depends_on=["dsri"],
                    ),
                }
            )
        )
        assert registry.metrics["m_score"].depends_on == ["dsri"]

    def test_invalid_depends_on_raises(self) -> None:
        with pytest.raises(ValidationError, match="depends_on.*nonexistent"):
            MetricRegistry.model_validate(
                _minimal_registry(
                    metrics={
                        "m_score": _minimal_entry(
                            display_name="M-Score",
                            depends_on=["nonexistent_metric"],
                        ),
                    }
                )
            )


# ---------------------------------------------------------------------------
# Test 8: Frozen model enforcement
# ---------------------------------------------------------------------------


class TestFrozenModels:
    """All models are frozen; assignment raises ValidationError."""

    def test_frozen_metric_definition(self) -> None:
        registry = MetricRegistry.model_validate(_minimal_registry())
        metric = registry.metrics["test_metric"]
        with pytest.raises(ValidationError):
            metric.display_name = "changed"  # type: ignore[misc]

    def test_frozen_tolerance(self) -> None:
        tol = Tolerance(absolute=0.05)
        with pytest.raises(ValidationError):
            tol.absolute = 0.01  # type: ignore[misc]

    def test_frozen_input_field(self) -> None:
        field = InputField(name="x", type="float")
        with pytest.raises(ValidationError):
            field.name = "y"  # type: ignore[misc]

    def test_frozen_reference_value(self) -> None:
        ref = ReferenceValue(
            name="test_ref",
            inputs={"x": 1.0},
            expected_output=2.0,
        )
        with pytest.raises(ValidationError):
            ref.name = "other"  # type: ignore[misc]

    def test_frozen_variant(self) -> None:
        var = Variant(function="svc.calculate_x")
        with pytest.raises(ValidationError):
            var.function = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 9: Tolerance model constraints
# ---------------------------------------------------------------------------


class TestToleranceConstraints:
    """Tolerance accepts absolute-only, relative-only, or both."""

    def test_absolute_only(self) -> None:
        tol = Tolerance(absolute=0.05)
        assert tol.absolute == 0.05
        assert tol.relative is None

    def test_relative_only(self) -> None:
        tol = Tolerance(relative=0.01)
        assert tol.relative == 0.01
        assert tol.absolute is None

    def test_both_absolute_and_relative(self) -> None:
        tol = Tolerance(absolute=0.05, relative=0.01)
        assert tol.absolute == 0.05
        assert tol.relative == 0.01

    def test_neither_raises(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            Tolerance()


# ---------------------------------------------------------------------------
# Test 10: MetricRegistry.from_yaml()
# ---------------------------------------------------------------------------


class TestFromYaml:
    """from_yaml() class method loads and validates a YAML string."""

    def test_from_yaml_valid(self) -> None:
        yaml_str = yaml.dump(
            _minimal_registry(
                metrics={
                    "test": _minimal_entry(display_name="Test"),
                }
            )
        )
        registry = MetricRegistry.from_yaml(yaml_str)
        assert "test" in registry.metrics
        assert registry.metrics["test"].display_name == "Test"

    def test_from_yaml_invalid(self) -> None:
        yaml_str = yaml.dump({"metrics": {"bad": {"category": "risk"}}})
        with pytest.raises(ValidationError):
            MetricRegistry.from_yaml(yaml_str)


# ---------------------------------------------------------------------------
# Test 11: ReferenceValue model
# ---------------------------------------------------------------------------


class TestReferenceValue:
    """ReferenceValue accepts name, inputs, expected_output, optional source."""

    def test_basic_reference_value(self) -> None:
        ref = ReferenceValue(
            name="beneish_1999_table3_sample1",
            inputs={"dsri": 1.2, "gmi": 1.1},
            expected_output=-2.22,
            source="Beneish 1999, Table 3",
        )
        assert ref.name == "beneish_1999_table3_sample1"
        assert ref.inputs["dsri"] == 1.2
        assert ref.expected_output == -2.22
        assert ref.source == "Beneish 1999, Table 3"

    def test_reference_value_dict_output(self) -> None:
        ref = ReferenceValue(
            name="multi_output",
            inputs={"x": 1.0},
            expected_output={"a": 1.0, "b": 2.0},
        )
        assert isinstance(ref.expected_output, dict)


# ---------------------------------------------------------------------------
# Test 12: InputField model
# ---------------------------------------------------------------------------


class TestInputField:
    """InputField accepts name (required) and optional fields."""

    def test_minimal_input_field(self) -> None:
        field = InputField(name="revenue", type="float")
        assert field.name == "revenue"
        assert field.type == "float"
        assert field.akshare_field is None
        assert field.efinance_field is None
        assert field.required is True
        assert field.description is None

    def test_full_input_field(self) -> None:
        field = InputField(
            name="revenue",
            type="Decimal",
            akshare_field="TOTAL_OPERATE_INCOME",
            efinance_field="total_revenue",
            required=True,
            description="Total operating revenue",
        )
        assert field.akshare_field == "TOTAL_OPERATE_INCOME"
        assert field.efinance_field == "total_revenue"
        assert field.description == "Total operating revenue"

    def test_input_field_optional_type(self) -> None:
        field = InputField(name="x", type="float")
        assert field.required is True
        field2 = InputField(name="y", type="str", required=False)
        assert field2.required is False


# ===========================================================================
# Task 2 tests: metric_registry.yaml end-to-end loading (Tests 13-20)
# ===========================================================================

REGISTRY_YAML_PATH = (
    Path(__file__).resolve().parents[3]
    / "stockvaluefinder"
    / "validation"
    / "metric_registry.yaml"
)


class TestRegistryYamlLoading:
    """End-to-end tests loading metric_registry.yaml from file."""

    @pytest.fixture
    def registry(self) -> MetricRegistry:
        """Load the actual metric_registry.yaml file."""
        with open(REGISTRY_YAML_PATH) as f:
            yaml_content = f.read()
        return MetricRegistry.from_yaml(yaml_content)

    def test_13_load_yaml_from_file(self, registry: MetricRegistry) -> None:
        """Test 13: Loading metric_registry.yaml via from_yaml() succeeds."""
        assert registry is not None
        assert len(registry.metrics) > 0

    def test_14_contains_all_metrics(self, registry: MetricRegistry) -> None:
        """Test 14: Loaded registry has >= 28 metric entries."""
        assert len(registry.metrics) >= 28

    def test_15_risk_category_metrics(self, registry: MetricRegistry) -> None:
        """Test 15: metrics_by_category('risk') returns risk metrics."""
        risk_metrics = registry.metrics_by_category("risk")
        risk_names = [name for name, _ in risk_metrics]
        assert "dsri" in risk_names
        assert "gmi" in risk_names
        assert "aqi" in risk_names
        assert "sgi" in risk_names
        assert "depi" in risk_names
        assert "sgai" in risk_names
        assert "lvgi" in risk_names
        assert "tata" in risk_names
        assert "m_score" in risk_names
        assert "f_score" in risk_names

    def test_16_roic_category_metrics(self, registry: MetricRegistry) -> None:
        """Test 16: metrics_by_category('roic') returns ROIC metrics."""
        roic_metrics = registry.metrics_by_category("roic")
        roic_names = [name for name, _ in roic_metrics]
        assert "nopat" in roic_names
        assert "invested_capital" in roic_names
        assert "roic" in roic_names
        assert "roic_wacc_spread" in roic_names

    def test_17_nopat_has_variants(self, registry: MetricRegistry) -> None:
        """Test 17: nopat metric has financial and non_financial variants."""
        nopat = registry.metrics["nopat"]
        assert "financial" in nopat.variants
        assert "non_financial" in nopat.variants

    def test_18_m_score_depends_on_eight_subindices(
        self, registry: MetricRegistry
    ) -> None:
        """Test 18: m_score depends_on lists all 8 sub-indices."""
        m_score = registry.metrics["m_score"]
        expected_deps = {"dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"}
        assert set(m_score.depends_on) == expected_deps

    def test_19_all_metrics_have_tolerance(self, registry: MetricRegistry) -> None:
        """Test 19: Every metric entry has a non-empty tolerance."""
        for name, metric in registry.all_metrics():
            assert metric.tolerance is not None, f"Metric {name} missing tolerance"
            has_abs = metric.tolerance.absolute is not None
            has_rel = metric.tolerance.relative is not None
            assert has_abs or has_rel, (
                f"Metric {name} has neither absolute nor relative tolerance"
            )

    def test_20_p0_metrics(self, registry: MetricRegistry) -> None:
        """Test 20: p0_metrics() returns expected P0 metrics."""
        p0_names = [name for name, _ in registry.p0_metrics()]
        expected_p0 = [
            "m_score",
            "f_score",
            "nopat",
            "invested_capital",
            "roic",
            "roic_wacc_spread",
        ]
        for expected in expected_p0:
            assert expected in p0_names, f"{expected} not in P0 metrics"
