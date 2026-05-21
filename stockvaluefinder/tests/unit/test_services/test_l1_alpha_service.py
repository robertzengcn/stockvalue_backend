"""L1 formula verification tests for alpha_service pure functions.

Verifies all four normalization functions (ROIC-WACC spread, CapEx grade,
policy score, moat trend), the composite Alpha score with fixed weights
(40/30/20/10), and Alpha level classification.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.capital_allocation import CapitalAllocationGrade
from stockvaluefinder.models.enums import AlphaLevel
from stockvaluefinder.models.roic import MoatTrend
from stockvaluefinder.services.alpha_service import (
    calculate_alpha_score,
    classify_alpha_level,
    normalize_capex_score,
    normalize_moat_score,
    normalize_policy_score,
    normalize_roic_wacc_score,
)


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1Normalization:
    """L1 tests for the four normalization functions.

    normalize_roic_wacc_score: Clamp [-0.10, +0.10], linear to [0, 100]
    normalize_capex_score: A=100, B=75, C=50, D=25
    normalize_policy_score: Pass-through clamp [0, 100]
    normalize_moat_score: COMPETITIVE_ADVANTAGE=100, STABLE=50, else=0
    """

    def test_roic_wacc_none(self) -> None:
        """None spread -> 0.0."""
        assert normalize_roic_wacc_score(None) == 0.0

    def test_roic_wacc_min(self) -> None:
        """spread=-0.10 (clamped min) -> 0.0."""
        assert normalize_roic_wacc_score(-0.10) == 0.0

    def test_roic_wacc_max(self) -> None:
        """spread=0.10 (clamped max) -> 100.0."""
        assert normalize_roic_wacc_score(0.10) == 100.0

    def test_roic_wacc_zero(self) -> None:
        """spread=0.0 (midpoint) -> 50.0."""
        assert normalize_roic_wacc_score(0.0) == 50.0

    def test_roic_wacc_positive(self) -> None:
        """spread=0.05 (halfway) -> 75.0."""
        assert normalize_roic_wacc_score(0.05) == 75.0

    def test_capex_grade_a(self) -> None:
        """Grade A -> 100."""
        assert normalize_capex_score(CapitalAllocationGrade.A) == 100.0

    def test_capex_grade_b(self) -> None:
        """Grade B -> 75."""
        assert normalize_capex_score(CapitalAllocationGrade.B) == 75.0

    def test_capex_grade_c(self) -> None:
        """Grade C -> 50."""
        assert normalize_capex_score(CapitalAllocationGrade.C) == 50.0

    def test_capex_grade_d(self) -> None:
        """Grade D -> 25."""
        assert normalize_capex_score(CapitalAllocationGrade.D) == 25.0

    def test_policy_score_pass_through(self) -> None:
        """Score 75 -> 75 (pass-through)."""
        assert normalize_policy_score(75.0) == 75.0

    def test_policy_score_clamp_negative(self) -> None:
        """Score -5 -> 0 (clamped)."""
        assert normalize_policy_score(-5.0) == 0.0

    def test_policy_score_clamp_over_100(self) -> None:
        """Score 150 -> 100 (clamped)."""
        assert normalize_policy_score(150.0) == 100.0

    def test_moat_competitive(self) -> None:
        """COMPETITIVE_ADVANTAGE -> 100."""
        assert normalize_moat_score(MoatTrend.COMPETITIVE_ADVANTAGE) == 100.0

    def test_moat_stable(self) -> None:
        """STABLE -> 50."""
        assert normalize_moat_score(MoatTrend.STABLE) == 50.0

    def test_moat_deteriorating(self) -> None:
        """DETERIORATING -> 0."""
        assert normalize_moat_score(MoatTrend.DETERIORATING) == 0.0

    def test_moat_none(self) -> None:
        """None -> 0."""
        assert normalize_moat_score(None) == 0.0


# ---------------------------------------------------------------------------
# Alpha composite score
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1AlphaScore:
    """L1 tests for composite Alpha score calculation.

    Default weights: (0.40, 0.30, 0.20, 0.10) for ROIC/CapEx/Policy/Moat.
    """

    def test_all_100(self) -> None:
        """All 100: 100*0.4 + 100*0.3 + 100*0.2 + 100*0.1 = 100.0."""
        score = calculate_alpha_score(100.0, 100.0, 100.0, 100.0)
        assert score == pytest.approx(100.0, abs=1e-6)

    def test_mixed_scores(self) -> None:
        """[100, 75, 50, 0]: 100*0.4 + 75*0.3 + 50*0.2 + 0*0.1 = 72.5."""
        score = calculate_alpha_score(100.0, 75.0, 50.0, 0.0)
        assert score == pytest.approx(72.5, abs=1e-6)

    def test_all_zero(self) -> None:
        """All 0: 0.0."""
        score = calculate_alpha_score(0.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_custom_weights(self) -> None:
        """Custom weights (1.0, 0.0, 0.0, 0.0) with score [80, 0, 0, 0] -> 80.0."""
        score = calculate_alpha_score(80.0, 0.0, 0.0, 0.0, weights=(1.0, 0.0, 0.0, 0.0))
        assert score == pytest.approx(80.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Alpha level classification
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1AlphaLevel:
    """L1 tests for Alpha level classification.

    Tier boundaries:
    - EXCELLENT: >= 80
    - GOOD: >= 60
    - FAIR: >= 40
    - WEAK: >= 20
    - POOR: < 20
    """

    def test_excellent(self) -> None:
        """score=100 -> EXCELLENT."""
        assert classify_alpha_level(100.0) == AlphaLevel.EXCELLENT

    def test_good(self) -> None:
        """score=60 -> GOOD."""
        assert classify_alpha_level(60.0) == AlphaLevel.GOOD

    def test_fair(self) -> None:
        """score=40 -> FAIR."""
        assert classify_alpha_level(40.0) == AlphaLevel.FAIR

    def test_weak(self) -> None:
        """score=20 -> WEAK."""
        assert classify_alpha_level(20.0) == AlphaLevel.WEAK

    def test_poor(self) -> None:
        """score=0 -> POOR."""
        assert classify_alpha_level(0.0) == AlphaLevel.POOR
