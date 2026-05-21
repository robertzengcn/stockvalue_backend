"""L1 formula verification tests for policy_service pure functions.

Verifies resonance score calculation (weighted cosine + confidence), resonance
tier classification at boundaries, and DCF terminal growth adjustment with
clamping.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.enums import ResonanceTier
from stockvaluefinder.services.policy_service import (
    calculate_dcf_adjustment,
    calculate_resonance_score,
    classify_resonance_tier,
)


# ---------------------------------------------------------------------------
# Resonance score
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ResonanceScore:
    """L1 tests for resonance score calculation.

    Formula: score = 60% * (avg_cosine * 100) + 40% * (avg_confidence * 100)
    Only relevant=True matches contribute. Returns 0.0 if no relevant matches.
    """

    def test_two_relevant_matches(self) -> None:
        """Two relevant matches: score=82.0.

        avg_cosine = (0.85+0.75)/2 = 0.80
        avg_confidence = (0.9+0.8)/2 = 0.85
        score = 0.6*(0.80*100) + 0.4*(0.85*100) = 48+34 = 82.0
        """
        matches = [
            {"score": 0.85, "relevant": True, "confidence": 0.9},
            {"score": 0.75, "relevant": True, "confidence": 0.8},
        ]
        score = calculate_resonance_score(matches)
        assert score == pytest.approx(82.0, abs=1e-6)

    def test_all_non_relevant(self) -> None:
        """All non-relevant matches -> 0.0."""
        matches = [
            {"score": 0.85, "relevant": False, "confidence": 0.1},
        ]
        score = calculate_resonance_score(matches)
        assert score == 0.0

    def test_empty_list(self) -> None:
        """Empty match list -> 0.0."""
        score = calculate_resonance_score([])
        assert score == 0.0


# ---------------------------------------------------------------------------
# Resonance tier
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ResonanceTier:
    """L1 tests for resonance tier classification.

    Thresholds:
    - STRONGLY_SUPPORTIVE: >= 80
    - SUPPORTIVE: >= 40
    - NEUTRAL: < 40
    """

    def test_strongly_supportive(self) -> None:
        """score=85.0 -> STRONGLY_SUPPORTIVE (>=80)."""
        tier = classify_resonance_tier(85.0)
        assert tier == ResonanceTier.STRONGLY_SUPPORTIVE

    def test_supportive(self) -> None:
        """score=60.0 -> SUPPORTIVE (>=40)."""
        tier = classify_resonance_tier(60.0)
        assert tier == ResonanceTier.SUPPORTIVE

    def test_neutral(self) -> None:
        """score=30.0 -> NEUTRAL (<40)."""
        tier = classify_resonance_tier(30.0)
        assert tier == ResonanceTier.NEUTRAL


# ---------------------------------------------------------------------------
# DCF adjustment
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1DCFAdjustment:
    """L1 tests for DCF terminal growth adjustment.

    Tier-based adjustment:
    - Strongly Supportive: +1.5% (0.015)
    - Supportive: +1.0% (0.01)
    - Neutral: 0%

    Adjusted value clamped at max_terminal_growth.
    """

    def test_strongly_supportive_adjustment(self) -> None:
        """Score 85 (Strongly Supportive), original=0.025 -> adjusted=0.04.

        adjustment = +0.015
        adjusted = 0.025 + 0.015 = 0.04
        """
        result = calculate_dcf_adjustment(85.0, 0.025)
        assert result.adjustment_pct == pytest.approx(0.015, abs=1e-6)
        assert result.adjusted_terminal_growth == pytest.approx(0.04, abs=1e-6)
        assert result.tier == ResonanceTier.STRONGLY_SUPPORTIVE

    def test_supportive_adjustment(self) -> None:
        """Score 60 (Supportive), original=0.025 -> adjusted=0.035.

        adjustment = +0.01
        adjusted = 0.025 + 0.01 = 0.035
        """
        result = calculate_dcf_adjustment(60.0, 0.025)
        assert result.adjustment_pct == pytest.approx(0.01, abs=1e-6)
        assert result.adjusted_terminal_growth == pytest.approx(0.035, abs=1e-6)
        assert result.tier == ResonanceTier.SUPPORTIVE

    def test_neutral_adjustment(self) -> None:
        """Score 30 (Neutral), original=0.025 -> adjusted=0.025 (no change).

        adjustment = 0.0
        adjusted = 0.025 + 0.0 = 0.025
        """
        result = calculate_dcf_adjustment(30.0, 0.025)
        assert result.adjustment_pct == pytest.approx(0.0, abs=1e-6)
        assert result.adjusted_terminal_growth == pytest.approx(0.025, abs=1e-6)
        assert result.tier == ResonanceTier.NEUTRAL

    def test_clamped_at_max(self) -> None:
        """Score 90 (Strongly Supportive), original=0.095, max=0.10 -> clamped to 0.10.

        adjustment = +0.015
        adjusted = 0.095 + 0.015 = 0.11, clamped to 0.10
        """
        result = calculate_dcf_adjustment(90.0, 0.095, max_terminal_growth=0.10)
        assert result.adjusted_terminal_growth == pytest.approx(0.10, abs=1e-6)
        assert result.adjustment_pct == pytest.approx(0.015, abs=1e-6)
