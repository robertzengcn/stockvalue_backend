"""Tests for the metric registry loader and registry.check() method.

Covers:
- load_metric_registry() returns a MetricRegistry instance
- load_metric_registry() returns the same cached instance on repeated calls
- registry.check() with known metric returns ComparisonResult
- registry.check() with sector variant uses variant tolerance
- registry.check() raises KeyError for unknown metric name
- load_metric_registry() works from any working directory (package-relative path)
"""

import os

import pytest

from stockvaluefinder.validation.loader import load_metric_registry
from stockvaluefinder.validation.schema import MetricRegistry


class TestLoaderSingleton:
    """lru_cache singleton behavior for load_metric_registry()."""

    def test_returns_metric_registry(self) -> None:
        """Test 8: load_metric_registry() returns a MetricRegistry instance."""
        registry = load_metric_registry()
        assert isinstance(registry, MetricRegistry)

    def test_returns_same_instance(self) -> None:
        """Test 9: Called twice returns the same object (lru_cache singleton)."""
        registry1 = load_metric_registry()
        registry2 = load_metric_registry()
        assert registry1 is registry2

    def test_registry_has_metrics(self) -> None:
        """Loaded registry contains expected metrics."""
        registry = load_metric_registry()
        assert len(registry.metrics) >= 28

    def test_loader_uses_package_relative_path(self) -> None:
        """Test 14: Loader works regardless of current working directory."""
        # Save current directory
        original_cwd = os.getcwd()
        try:
            # Change to a different directory
            os.chdir("/tmp")
            # Clear the lru_cache to force a reload
            load_metric_registry.cache_clear()
            registry = load_metric_registry()
            assert isinstance(registry, MetricRegistry)
            assert len(registry.metrics) >= 28
        finally:
            os.chdir(original_cwd)
            # Clear cache again to not affect other tests
            load_metric_registry.cache_clear()


class TestRegistryCheck:
    """registry.check() method tests."""

    @pytest.fixture
    def registry(self) -> MetricRegistry:
        """Provide a fresh registry instance."""
        load_metric_registry.cache_clear()
        return load_metric_registry()

    def test_check_known_metric(self, registry: MetricRegistry) -> None:
        """Test 10: registry.check('m_score', -2.5, -2.52) uses m_score tolerance."""
        result = registry.check("m_score", -2.5, -2.52)
        assert result.metric_name == "m_score"
        assert result.expected == pytest.approx(-2.5)
        assert result.computed == pytest.approx(-2.52)
        # m_score tolerance is absolute=0.05, delta is 0.02 => should pass
        assert result.passed is True

    def test_check_known_metric_fails(self, registry: MetricRegistry) -> None:
        """registry.check() fails when delta exceeds tolerance."""
        # m_score tolerance is absolute=0.05, delta 0.1 => should fail
        result = registry.check("m_score", -2.5, -2.6)
        assert result.passed is False

    def test_check_with_sector_variant(self, registry: MetricRegistry) -> None:
        """Test 11: registry.check('nopat', 100, 101, sector='non_financial') uses variant."""
        result = registry.check("nopat", 100.0, 101.0, sector="non_financial")
        assert result.metric_name == "nopat"
        # nopat non_financial variant has relative=0.02
        # delta=1.0, relative=1.0% < 2% => pass
        assert result.passed is True

    def test_check_unknown_metric_raises(self, registry: MetricRegistry) -> None:
        """Test 12: registry.check() raises KeyError for unknown metric name."""
        with pytest.raises(KeyError, match="nonexistent_metric"):
            registry.check("nonexistent_metric", 1.0, 2.0)

    def test_check_returns_comparison_result(self, registry: MetricRegistry) -> None:
        """registry.check() returns a ComparisonResult with all fields."""
        from stockvaluefinder.validation.comparators import ComparisonResult

        result = registry.check("m_score", -2.5, -2.52)
        assert isinstance(result, ComparisonResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "expected")
        assert hasattr(result, "computed")
        assert hasattr(result, "delta")
        assert hasattr(result, "tolerance_applied")
        assert hasattr(result, "metric_name")

    def test_check_with_dsri(self, registry: MetricRegistry) -> None:
        """registry.check() works for sub-index metrics like dsri."""
        result = registry.check("dsri", 1.2, 1.23)
        # dsri tolerance is absolute=0.05, delta=0.03 => pass
        assert result.passed is True

    def test_check_with_dsri_fails(self, registry: MetricRegistry) -> None:
        """registry.check() fails for dsri when delta exceeds tolerance."""
        result = registry.check("dsri", 1.2, 1.3)
        # dsri tolerance is absolute=0.05, delta=0.1 => fail
        assert result.passed is False
