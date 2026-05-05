"""Unit tests for capital allocation domain models and config (TDD RED phase)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from stockvaluefinder.config import (
    AppConfig,
    CapitalAllocationConfig,
    capital_allocation_config,
)
from stockvaluefinder.models.capital_allocation import (
    BuybackYieldResult,
    CapitalAllocationGrade,
    CapitalAllocationRequest,
    CapitalAllocationResult,
    CapitalAllocationScoreCreate,
    DividendStabilityResult,
    DividendTrend,
    ExpansionDisciplineResult,
)


class TestCapitalAllocationGradeEnum:
    """Tests for CapitalAllocationGrade enum values."""

    def test_grade_a(self) -> None:
        """Grade A exists with correct value."""
        assert CapitalAllocationGrade.A == "A"
        assert CapitalAllocationGrade.A.value == "A"

    def test_grade_b(self) -> None:
        """Grade B exists with correct value."""
        assert CapitalAllocationGrade.B == "B"
        assert CapitalAllocationGrade.B.value == "B"

    def test_grade_c(self) -> None:
        """Grade C exists with correct value."""
        assert CapitalAllocationGrade.C == "C"
        assert CapitalAllocationGrade.C.value == "C"

    def test_grade_d(self) -> None:
        """Grade D exists with correct value."""
        assert CapitalAllocationGrade.D == "D"
        assert CapitalAllocationGrade.D.value == "D"

    def test_four_grades(self) -> None:
        """Exactly four grades exist: A, B, C, D."""
        assert len(CapitalAllocationGrade) == 4


class TestDividendTrendEnum:
    """Tests for DividendTrend enum values."""

    def test_growth(self) -> None:
        """GROWTH exists with correct value."""
        assert DividendTrend.GROWTH == "Growth"

    def test_decline(self) -> None:
        """DECLINE exists with correct value."""
        assert DividendTrend.DECLINE == "Decline"

    def test_stable(self) -> None:
        """STABLE exists with correct value."""
        assert DividendTrend.STABLE == "Stable"

    def test_insufficient_data(self) -> None:
        """INSUFFICIENT_DATA exists with correct value."""
        assert DividendTrend.INSUFFICIENT_DATA == "Insufficient Data"

    def test_four_trends(self) -> None:
        """Exactly four trends exist."""
        assert len(DividendTrend) == 4


class TestCapitalAllocationRequest:
    """Tests for CapitalAllocationRequest validation."""

    def test_valid_sh_ticker(self) -> None:
        """Valid Shanghai ticker accepted."""
        req = CapitalAllocationRequest(ticker="600519.SH")
        assert req.ticker == "600519.SH"

    def test_valid_sz_ticker(self) -> None:
        """Valid Shenzhen ticker accepted."""
        req = CapitalAllocationRequest(ticker="000001.SZ")
        assert req.ticker == "000001.SZ"

    def test_valid_hk_ticker(self) -> None:
        """Valid Hong Kong ticker accepted (6-digit pattern per project convention)."""
        req = CapitalAllocationRequest(ticker="007000.HK")
        assert req.ticker == "007000.HK"

    def test_year_optional(self) -> None:
        """Year is optional and defaults to None."""
        req = CapitalAllocationRequest(ticker="600519.SH")
        assert req.year is None

    def test_year_provided(self) -> None:
        """Year can be provided."""
        req = CapitalAllocationRequest(ticker="600519.SH", year=2023)
        assert req.year == 2023

    def test_invalid_ticker_no_dot(self) -> None:
        """Ticker without dot suffix is rejected."""
        with pytest.raises(ValidationError):
            CapitalAllocationRequest(ticker="600519")

    def test_invalid_ticker_wrong_suffix(self) -> None:
        """Ticker with wrong suffix is rejected."""
        with pytest.raises(ValidationError):
            CapitalAllocationRequest(ticker="600519.US")

    def test_invalid_ticker_too_few_digits(self) -> None:
        """Ticker with fewer than 6 digits is rejected."""
        with pytest.raises(ValidationError):
            CapitalAllocationRequest(ticker="6019.SH")

    def test_invalid_ticker_too_many_digits(self) -> None:
        """Ticker with more than 6 digits is rejected."""
        with pytest.raises(ValidationError):
            CapitalAllocationRequest(ticker="60005190.SH")


class TestBuybackYieldResult:
    """Tests for BuybackYieldResult frozen model."""

    def test_create_complete(self) -> None:
        """Create result with all fields."""
        result = BuybackYieldResult(
            buyback_yield=0.02,
            repurchase_amount=100_000_000,
            market_cap=5_000_000_000,
            data_quality="COMPLETE",
            grade=CapitalAllocationGrade.A,
        )
        assert result.buyback_yield == 0.02
        assert result.data_quality == "COMPLETE"
        assert result.grade == CapitalAllocationGrade.A

    def test_frozen(self) -> None:
        """Model is frozen and rejects modification."""
        result = BuybackYieldResult(
            buyback_yield=None,
            repurchase_amount=None,
            market_cap=None,
            data_quality="INCOMPLETE",
            grade=CapitalAllocationGrade.D,
        )
        with pytest.raises(ValidationError):
            result.buyback_yield = 0.01  # type: ignore[misc]


class TestDividendStabilityResult:
    """Tests for DividendStabilityResult frozen model."""

    def test_create_growth(self) -> None:
        """Create result with GROWTH classification."""
        result = DividendStabilityResult(
            classification=DividendTrend.GROWTH,
            slope=0.1,
            p_value=0.01,
            data_points=5,
            dpu_values=[1.0, 1.1, 1.2, 1.3, 1.4],
            grade=CapitalAllocationGrade.A,
        )
        assert result.classification == DividendTrend.GROWTH
        assert result.data_points == 5
        assert len(result.dpu_values) == 5

    def test_frozen(self) -> None:
        """Model is frozen and rejects modification."""
        result = DividendStabilityResult(
            classification=DividendTrend.STABLE,
            slope=0.0,
            p_value=1.0,
            data_points=3,
            dpu_values=[1.0, 1.0, 1.0],
            grade=CapitalAllocationGrade.B,
        )
        with pytest.raises(ValidationError):
            result.classification = DividendTrend.DECLINE  # type: ignore[misc]


class TestExpansionDisciplineResult:
    """Tests for ExpansionDisciplineResult frozen model."""

    def test_create_alert(self) -> None:
        """Create result with blind expansion alert."""
        result = ExpansionDisciplineResult(
            alert=True,
            roic_wacc_spread=-0.05,
            capex_yoy_growth=0.5,
            capex_current=150,
            capex_previous=100,
            reason=None,
            grade=CapitalAllocationGrade.C,
        )
        assert result.alert is True
        assert result.roic_wacc_spread == -0.05

    def test_create_no_alert(self) -> None:
        """Create result without alert."""
        result = ExpansionDisciplineResult(
            alert=False,
            roic_wacc_spread=0.05,
            capex_yoy_growth=0.1,
            capex_current=110,
            capex_previous=100,
            reason="value_creating",
            grade=CapitalAllocationGrade.A,
        )
        assert result.alert is False
        assert result.reason == "value_creating"

    def test_frozen(self) -> None:
        """Model is frozen."""
        result = ExpansionDisciplineResult(
            alert=False,
            roic_wacc_spread=None,
            capex_yoy_growth=None,
            capex_current=None,
            capex_previous=None,
            reason="insufficient_data",
            grade=CapitalAllocationGrade.C,
        )
        with pytest.raises(ValidationError):
            result.alert = True  # type: ignore[misc]


class TestCapitalAllocationResult:
    """Tests for CapitalAllocationResult frozen model."""

    def _make_result(self) -> CapitalAllocationResult:
        """Helper to create a valid CapitalAllocationResult."""
        return CapitalAllocationResult(
            ticker="600519.SH",
            fiscal_year=2023,
            buyback_yield=BuybackYieldResult(
                buyback_yield=0.02,
                repurchase_amount=100_000_000,
                market_cap=5_000_000_000,
                data_quality="COMPLETE",
                grade=CapitalAllocationGrade.A,
            ),
            dividend_stability=DividendStabilityResult(
                classification=DividendTrend.STABLE,
                slope=0.0,
                p_value=1.0,
                data_points=5,
                dpu_values=[1.0, 1.0, 1.0, 1.0, 1.0],
                grade=CapitalAllocationGrade.B,
            ),
            expansion_discipline=ExpansionDisciplineResult(
                alert=False,
                roic_wacc_spread=0.05,
                capex_yoy_growth=0.1,
                capex_current=110,
                capex_previous=100,
                reason="value_creating",
                grade=CapitalAllocationGrade.A,
            ),
            overall_grade=CapitalAllocationGrade.A,
            weighting={
                "buyback_yield": 0.333,
                "dividend_stability": 0.333,
                "expansion_discipline": 0.334,
            },
            calculated_at=datetime.now(timezone.utc),
        )

    def test_create_full(self) -> None:
        """Create full result with all nested models."""
        result = self._make_result()
        assert result.ticker == "600519.SH"
        assert result.fiscal_year == 2023
        assert result.overall_grade == CapitalAllocationGrade.A
        assert "buyback_yield" in result.weighting

    def test_frozen(self) -> None:
        """Model is frozen."""
        result = self._make_result()
        with pytest.raises(ValidationError):
            result.ticker = "000001.SZ"  # type: ignore[misc]

    def test_audit_trail_default(self) -> None:
        """audit_trail defaults to empty dict."""
        result = self._make_result()
        assert result.audit_trail == {}


class TestCapitalAllocationScoreCreate:
    """Tests for CapitalAllocationScoreCreate model."""

    def test_create(self) -> None:
        """Create score for DB persistence."""
        from uuid import uuid4

        create = CapitalAllocationScoreCreate(
            analysis_id=uuid4(),
            ticker="600519.SH",
            fiscal_year=2023,
            buyback_yield_data={"buyback_yield": 0.02},
            dividend_stability_data={"classification": "Growth"},
            expansion_discipline_data={"alert": False},
            overall_grade="A",
            weighting={
                "buyback_yield": 0.333,
                "dividend_stability": 0.333,
                "expansion_discipline": 0.334,
            },
            audit_trail={},
        )
        assert create.ticker == "600519.SH"
        assert create.overall_grade == "A"


class TestCapitalAllocationConfig:
    """Tests for CapitalAllocationConfig frozen dataclass."""

    def test_default_capex_growth_threshold(self) -> None:
        """CAPEX_GROWTH_THRESHOLD defaults to 0.20."""
        config = CapitalAllocationConfig()
        assert config.CAPEX_GROWTH_THRESHOLD == 0.20

    def test_default_dpu_trend_threshold(self) -> None:
        """DPU_TREND_THRESHOLD defaults to 0.05."""
        config = CapitalAllocationConfig()
        assert config.DPU_TREND_THRESHOLD == 0.05

    def test_default_min_dpu_data_points(self) -> None:
        """MIN_DPU_DATA_POINTS defaults to 3."""
        config = CapitalAllocationConfig()
        assert config.MIN_DPU_DATA_POINTS == 3

    def test_frozen(self) -> None:
        """Config is frozen and cannot be modified."""
        config = CapitalAllocationConfig()
        with pytest.raises(AttributeError):
            config.CAPEX_GROWTH_THRESHOLD = 0.30  # type: ignore[misc]

    def test_buyback_yield_grade_boundaries(self) -> None:
        """Buyback yield grade boundaries are set correctly."""
        config = CapitalAllocationConfig()
        assert config.BUYBACK_YIELD_GRADE_A == 0.02
        assert config.BUYBACK_YIELD_GRADE_B == 0.01
        assert config.BUYBACK_YIELD_GRADE_C == 0.005

    def test_overall_grade_thresholds(self) -> None:
        """Overall grade thresholds are set correctly."""
        config = CapitalAllocationConfig()
        assert config.OVERALL_GRADE_A_THRESHOLD == 3.5
        assert config.OVERALL_GRADE_B_THRESHOLD == 2.5
        assert config.OVERALL_GRADE_C_THRESHOLD == 1.5

    def test_dimension_weights_equal(self) -> None:
        """Dimension weights are equal (1/3 each)."""
        config = CapitalAllocationConfig()
        assert len(config.DIMENSION_WEIGHTS) == 3
        for w in config.DIMENSION_WEIGHTS:
            assert abs(w - 1.0 / 3) < 1e-10

    def test_expansion_alert_grade_c_threshold(self) -> None:
        """Expansion alert grade C threshold is 0.50."""
        config = CapitalAllocationConfig()
        assert config.EXPANSION_ALERT_GRADE_C_THRESHOLD == 0.50


class TestAppConfigIncludesCapitalAllocation:
    """Tests for AppConfig.get_instance() including capital_allocation field."""

    def test_app_config_has_capital_allocation(self) -> None:
        """AppConfig.get_instance() returns config with capital_allocation."""
        config = AppConfig.get_instance()
        assert hasattr(config, "capital_allocation")
        assert isinstance(config.capital_allocation, CapitalAllocationConfig)

    def test_global_config_instance(self) -> None:
        """Global capital_allocation_config is a CapitalAllocationConfig."""
        assert isinstance(capital_allocation_config, CapitalAllocationConfig)
        assert capital_allocation_config.CAPEX_GROWTH_THRESHOLD == 0.20
