"""Tests for screening and scoring Pydantic models.

TDD: Tests written before implementation (RED), implementation added (GREEN).
Covers: ScreeningSnapshot, ScreeningResult, CompositeScoreComponents,
        CompositeScore, CandidateReasons validation and structure.
"""

import pytest
from pydantic import ValidationError

from stockvaluefinder.market_scanner.models import (
    CandidateReasons,
    CompositeScore,
    CompositeScoreComponents,
    ScreeningResult,
    ScreeningSnapshot,
)


# ---------------------------------------------------------------------------
# ScreeningSnapshot tests
# ---------------------------------------------------------------------------


class TestScreeningSnapshot:
    """Test ScreeningSnapshot Pydantic model validation."""

    def _make_valid_snapshot(self, **overrides: object) -> dict[str, object]:
        """Create a valid ScreeningSnapshot data dict with optional overrides."""
        base: dict[str, object] = {
            "ticker": "600519.SH",
            "name": "Kweichow Moutai",
            "index_code": "CSI300",
            "is_st": False,
            "is_suspended": False,
            "has_price_data": True,
            "turnover_ratio": 0.05,
            "pe_ttm": 35.2,
            "pb_ratio": 12.8,
            "dividend_yield": 0.015,
            "price_vs_52w_high": 0.85,
            "ocf_positive_years": 5,
            "market_cap": 2_000_000_000_000,
        }
        base.update(overrides)
        return base

    def test_accepts_valid_snapshot(self) -> None:
        """ScreeningSnapshot should accept all valid required fields."""
        data = self._make_valid_snapshot()
        snapshot = ScreeningSnapshot(**data)

        assert snapshot.ticker == "600519.SH"
        assert snapshot.name == "Kweichow Moutai"
        assert snapshot.index_code == "CSI300"
        assert snapshot.is_st is False
        assert snapshot.is_suspended is False
        assert snapshot.has_price_data is True
        assert snapshot.turnover_ratio == pytest.approx(0.05)
        assert snapshot.pe_ttm == pytest.approx(35.2)
        assert snapshot.pb_ratio == pytest.approx(12.8)
        assert snapshot.dividend_yield == pytest.approx(0.015)
        assert snapshot.price_vs_52w_high == pytest.approx(0.85)
        assert snapshot.ocf_positive_years == 5
        assert snapshot.market_cap == pytest.approx(2_000_000_000_000)

    def test_rejects_invalid_ticker_format(self) -> None:
        """ScreeningSnapshot must reject ticker not matching NNNNNN.{SH|SZ}."""
        data = self._make_valid_snapshot(ticker="0700.HK")
        with pytest.raises(ValidationError, match="ticker"):
            ScreeningSnapshot(**data)

    def test_rejects_ticker_without_suffix(self) -> None:
        """ScreeningSnapshot must reject bare numeric ticker."""
        data = self._make_valid_snapshot(ticker="600519")
        with pytest.raises(ValidationError, match="ticker"):
            ScreeningSnapshot(**data)

    def test_rejects_negative_turnover_ratio(self) -> None:
        """ScreeningSnapshot must reject negative turnover_ratio."""
        data = self._make_valid_snapshot(turnover_ratio=-0.01)
        with pytest.raises(ValidationError, match="turnover_ratio"):
            ScreeningSnapshot(**data)

    def test_rejects_zero_market_cap(self) -> None:
        """ScreeningSnapshot must reject market_cap <= 0."""
        data = self._make_valid_snapshot(market_cap=0)
        with pytest.raises(ValidationError, match="market_cap"):
            ScreeningSnapshot(**data)

    def test_rejects_price_vs_52w_high_above_one(self) -> None:
        """ScreeningSnapshot must reject price_vs_52w_high > 1.0."""
        data = self._make_valid_snapshot(price_vs_52w_high=1.5)
        with pytest.raises(ValidationError, match="price_vs_52w_high"):
            ScreeningSnapshot(**data)

    def test_accepts_none_pe_ttm(self) -> None:
        """ScreeningSnapshot should accept None for pe_ttm (negative earnings)."""
        data = self._make_valid_snapshot(pe_ttm=None)
        snapshot = ScreeningSnapshot(**data)
        assert snapshot.pe_ttm is None

    def test_accepts_none_pb_ratio(self) -> None:
        """ScreeningSnapshot should accept None for pb_ratio."""
        data = self._make_valid_snapshot(pb_ratio=None)
        snapshot = ScreeningSnapshot(**data)
        assert snapshot.pb_ratio is None

    def test_defaults_optional_fields(self) -> None:
        """ScreeningSnapshot should use defaults for optional fields."""
        data = self._make_valid_snapshot()
        del data["pe_ttm"]
        del data["pb_ratio"]
        del data["dividend_yield"]
        del data["ocf_positive_years"]
        snapshot = ScreeningSnapshot(**data)

        assert snapshot.pe_ttm is None
        assert snapshot.pb_ratio is None
        assert snapshot.dividend_yield == pytest.approx(0.0)
        assert snapshot.ocf_positive_years == 0


# ---------------------------------------------------------------------------
# ScreeningResult tests
# ---------------------------------------------------------------------------


class TestScreeningResult:
    """Test ScreeningResult Pydantic model validation."""

    def test_passed_result(self) -> None:
        """ScreeningResult with passed=True has excluded_reason=None."""
        result = ScreeningResult(
            ticker="600519.SH",
            passed=True,
            rank_score=85.5,
            signals={"pe_low": 1.0, "dividend_high": 0.5},
        )

        assert result.passed is True
        assert result.excluded_reason is None
        assert result.rank_score == pytest.approx(85.5)
        assert result.signals["pe_low"] == pytest.approx(1.0)

    def test_failed_result_has_excluded_reason(self) -> None:
        """ScreeningResult with passed=False must have excluded_reason."""
        result = ScreeningResult(
            ticker="000001.SZ",
            passed=False,
            excluded_reason="ST stock; Suspended",
        )

        assert result.passed is False
        assert result.excluded_reason == "ST stock; Suspended"
        assert result.rank_score == pytest.approx(0.0)

    def test_rank_score_non_negative(self) -> None:
        """ScreeningResult must reject negative rank_score."""
        with pytest.raises(ValidationError, match="rank_score"):
            ScreeningResult(
                ticker="600519.SH",
                passed=True,
                rank_score=-1.0,
            )

    def test_default_signals_empty_dict(self) -> None:
        """ScreeningResult signals defaults to empty dict."""
        result = ScreeningResult(ticker="600519.SH", passed=True)
        assert result.signals == {}


# ---------------------------------------------------------------------------
# CompositeScoreComponents tests
# ---------------------------------------------------------------------------


class TestCompositeScoreComponents:
    """Test CompositeScoreComponents Pydantic model validation."""

    def test_accepts_valid_components(self) -> None:
        """CompositeScoreComponents should accept all scores in [0, 100]."""
        components = CompositeScoreComponents(
            safety_margin=85.0,
            alpha=72.5,
            risk_penalty=100.0,
            yield_gap=50.0,
            valuation_percentile=30.0,
        )

        assert components.safety_margin == pytest.approx(85.0)
        assert components.alpha == pytest.approx(72.5)
        assert components.risk_penalty == pytest.approx(100.0)
        assert components.yield_gap == pytest.approx(50.0)
        assert components.valuation_percentile == pytest.approx(30.0)

    def test_rejects_score_below_zero(self) -> None:
        """CompositeScoreComponents must reject scores < 0."""
        with pytest.raises(ValidationError, match="safety_margin"):
            CompositeScoreComponents(
                safety_margin=-1.0,
                alpha=50.0,
                risk_penalty=50.0,
                yield_gap=50.0,
                valuation_percentile=50.0,
            )

    def test_rejects_score_above_100(self) -> None:
        """CompositeScoreComponents must reject scores > 100."""
        with pytest.raises(ValidationError, match="alpha"):
            CompositeScoreComponents(
                safety_margin=50.0,
                alpha=101.0,
                risk_penalty=50.0,
                yield_gap=50.0,
                valuation_percentile=50.0,
            )

    def test_accepts_boundary_values(self) -> None:
        """CompositeScoreComponents should accept 0 and 100 exactly."""
        components = CompositeScoreComponents(
            safety_margin=0.0,
            alpha=100.0,
            risk_penalty=0.0,
            yield_gap=100.0,
            valuation_percentile=0.0,
        )
        assert components.safety_margin == pytest.approx(0.0)
        assert components.alpha == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# CompositeScore tests
# ---------------------------------------------------------------------------


class TestCompositeScore:
    """Test CompositeScore Pydantic model validation."""

    def _make_valid_components(self) -> CompositeScoreComponents:
        """Create valid CompositeScoreComponents for testing."""
        return CompositeScoreComponents(
            safety_margin=70.0,
            alpha=60.0,
            risk_penalty=80.0,
            yield_gap=40.0,
            valuation_percentile=55.0,
        )

    def test_accepts_valid_composite(self) -> None:
        """CompositeScore should accept valid composite in [0, 100]."""
        components = self._make_valid_components()
        score = CompositeScore(
            composite=65.5,
            components=components,
            passed_threshold=True,
        )

        assert score.composite == pytest.approx(65.5)
        assert score.passed_threshold is True
        assert score.components.safety_margin == pytest.approx(70.0)

    def test_rejects_composite_below_zero(self) -> None:
        """CompositeScore must reject composite < 0."""
        components = self._make_valid_components()
        with pytest.raises(ValidationError, match="composite"):
            CompositeScore(
                composite=-1.0,
                components=components,
                passed_threshold=False,
            )

    def test_rejects_composite_above_100(self) -> None:
        """CompositeScore must reject composite > 100."""
        components = self._make_valid_components()
        with pytest.raises(ValidationError, match="composite"):
            CompositeScore(
                composite=101.0,
                components=components,
                passed_threshold=True,
            )

    def test_frozen(self) -> None:
        """CompositeScore model_config must be frozen."""
        components = self._make_valid_components()
        score = CompositeScore(
            composite=65.5,
            components=components,
            passed_threshold=True,
        )

        with pytest.raises(ValidationError, match="frozen"):
            score.composite = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CandidateReasons tests
# ---------------------------------------------------------------------------


class TestCandidateReasons:
    """Test CandidateReasons Pydantic model validation."""

    def test_accepts_valid_reasons_with_risk_flags(self) -> None:
        """CandidateReasons should accept valid reasons and at least one risk flag."""
        reasons = CandidateReasons(
            reasons=["Safety margin 45%, above 30% threshold", "Alpha score 85.2"],
            risk_flags=["Standard risk factors apply; review full analysis"],
        )

        assert len(reasons.reasons) == 2
        assert len(reasons.risk_flags) >= 1

    def test_requires_at_least_one_risk_flag(self) -> None:
        """CandidateReasons must reject empty risk_flags (PITFALLS Pitfall 6)."""
        with pytest.raises(ValidationError, match="risk_flags"):
            CandidateReasons(
                reasons=["Strong candidate"],
                risk_flags=[],
            )

    def test_accepts_empty_reasons(self) -> None:
        """CandidateReasons should accept empty reasons list."""
        reasons = CandidateReasons(
            reasons=[],
            risk_flags=["Risk level MEDIUM, M-Score=-1.50"],
        )
        assert reasons.reasons == []
        assert len(reasons.risk_flags) == 1

    def test_frozen(self) -> None:
        """CandidateReasons model_config must be frozen."""
        reasons = CandidateReasons(
            reasons=["test"],
            risk_flags=["risk"],
        )
        with pytest.raises((ValidationError, AttributeError)):
            reasons.reasons = ["another"]  # type: ignore[misc]

    def test_defaults_reasons_to_empty_list(self) -> None:
        """CandidateReasons reasons should default to empty list."""
        reasons = CandidateReasons(risk_flags=["risk flag"])
        assert reasons.reasons == []
