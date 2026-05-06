"""Unit tests for policy_service pure functions.

Tests cover:
- Resonance score calculation (D-04)
- Resonance tier classification (D-07)
- DCF terminal growth adjustment (D-07, D-08)
- LLM verification JSON parsing
- LLM metadata extraction JSON parsing

All tests use pure functions with no external dependencies.
"""

from stockvaluefinder.config import PolicyResonanceConfig
from stockvaluefinder.models.enums import ResonanceTier


# ---------------------------------------------------------------------------
# calculate_resonance_score
# ---------------------------------------------------------------------------


class TestCalculateResonanceScore:
    """Tests for calculate_resonance_score pure function."""

    def test_relevant_matches(self) -> None:
        """Score with 2 relevant matches: 0.6*(avg_cosine*100) + 0.4*(avg_confidence*100)."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        matches = [
            {
                "score": 0.85,
                "relevant": True,
                "confidence": 0.9,
                "reason": "direct match",
            },
            {
                "score": 0.75,
                "relevant": True,
                "confidence": 0.8,
                "reason": "related policy",
            },
            {
                "score": 0.60,
                "relevant": False,
                "confidence": 0.1,
                "reason": "unrelated",
            },
        ]
        result = calculate_resonance_score(matches)
        # avg_cosine = (0.85 + 0.75) / 2 = 0.80
        # avg_confidence = (0.9 + 0.8) / 2 = 0.85
        # score = 0.6 * (0.80 * 100) + 0.4 * (0.85 * 100) = 48.0 + 34.0 = 82.0
        assert result == 82.0

    def test_no_relevant_matches(self) -> None:
        """All matches irrelevant -> score = 0.0 (not NaN)."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        matches = [
            {
                "score": 0.85,
                "relevant": False,
                "confidence": 0.1,
                "reason": "unrelated",
            },
            {
                "score": 0.75,
                "relevant": False,
                "confidence": 0.2,
                "reason": "unrelated",
            },
        ]
        result = calculate_resonance_score(matches)
        assert result == 0.0
        # Ensure it is exactly 0.0, not NaN
        assert result == result  # NaN check: NaN != NaN

    def test_empty_matches(self) -> None:
        """Empty list -> score = 0.0."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        result = calculate_resonance_score([])
        assert result == 0.0

    def test_mixed_relevant(self) -> None:
        """Only relevant=True matches contribute to the score."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        matches = [
            {"score": 0.90, "relevant": True, "confidence": 0.95, "reason": "direct"},
            {"score": 0.80, "relevant": True, "confidence": 0.85, "reason": "related"},
            {
                "score": 0.70,
                "relevant": False,
                "confidence": 0.3,
                "reason": "unrelated",
            },
            {
                "score": 0.65,
                "relevant": False,
                "confidence": 0.2,
                "reason": "unrelated",
            },
        ]
        result = calculate_resonance_score(matches)
        # Only 2 relevant: avg_cosine = (0.90+0.80)/2 = 0.85, avg_conf = (0.95+0.85)/2 = 0.90
        # score = 0.6 * 85.0 + 0.4 * 90.0 = 51.0 + 36.0 = 87.0
        assert result == 87.0

    def test_single_relevant_match(self) -> None:
        """Single relevant match produces correct score."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        matches = [
            {"score": 0.80, "relevant": True, "confidence": 0.90, "reason": "match"},
        ]
        result = calculate_resonance_score(matches)
        # avg_cosine = 0.80, avg_confidence = 0.90
        # score = 0.6 * 80.0 + 0.4 * 90.0 = 48.0 + 36.0 = 84.0
        assert result == 84.0

    def test_custom_config(self) -> None:
        """Custom config overrides default weights."""
        from stockvaluefinder.services.policy_service import calculate_resonance_score

        custom_config = PolicyResonanceConfig(COSINE_WEIGHT=0.80, LLM_WEIGHT=0.20)
        matches = [
            {"score": 0.80, "relevant": True, "confidence": 0.90, "reason": "match"},
        ]
        result = calculate_resonance_score(matches, config=custom_config)
        # score = 0.8 * 80.0 + 0.2 * 90.0 = 64.0 + 18.0 = 82.0
        assert result == 82.0


# ---------------------------------------------------------------------------
# classify_resonance_tier
# ---------------------------------------------------------------------------


class TestClassifyResonanceTier:
    """Tests for classify_resonance_tier pure function."""

    def test_strongly_supportive_at_threshold(self) -> None:
        """Score exactly 80.0 -> STRONGLY_SUPPORTIVE."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(80.0)
        assert result == ResonanceTier.STRONGLY_SUPPORTIVE

    def test_strongly_supportive_above_threshold(self) -> None:
        """Score 95.0 -> STRONGLY_SUPPORTIVE."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(95.0)
        assert result == ResonanceTier.STRONGLY_SUPPORTIVE

    def test_supportive_at_threshold(self) -> None:
        """Score exactly 40.0 -> SUPPORTIVE."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(40.0)
        assert result == ResonanceTier.SUPPORTIVE

    def test_supportive_middle(self) -> None:
        """Score 60.0 -> SUPPORTIVE."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(60.0)
        assert result == ResonanceTier.SUPPORTIVE

    def test_neutral_below_threshold(self) -> None:
        """Score 39.9 -> NEUTRAL."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(39.9)
        assert result == ResonanceTier.NEUTRAL

    def test_neutral_zero(self) -> None:
        """Score 0.0 -> NEUTRAL."""
        from stockvaluefinder.services.policy_service import classify_resonance_tier

        result = classify_resonance_tier(0.0)
        assert result == ResonanceTier.NEUTRAL


# ---------------------------------------------------------------------------
# calculate_dcf_adjustment
# ---------------------------------------------------------------------------


class TestCalculateDCFAdjustment:
    """Tests for calculate_dcf_adjustment pure function."""

    def test_strongly_supportive(self) -> None:
        """Score 85.0 -> STRONGLY_SUPPORTIVE, adjustment +1.5%."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        result = calculate_dcf_adjustment(85.0, 0.025)
        assert result.tier == ResonanceTier.STRONGLY_SUPPORTIVE
        assert result.adjustment_pct == 0.015
        assert result.adjusted_terminal_growth == 0.04
        assert result.original_terminal_growth == 0.025

    def test_supportive(self) -> None:
        """Score 60.0 -> SUPPORTIVE, adjustment +1.0%."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        result = calculate_dcf_adjustment(60.0, 0.03)
        assert result.tier == ResonanceTier.SUPPORTIVE
        assert result.adjustment_pct == 0.01
        assert result.adjusted_terminal_growth == 0.04
        assert result.original_terminal_growth == 0.03

    def test_neutral(self) -> None:
        """Score 30.0 -> NEUTRAL, no adjustment."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        result = calculate_dcf_adjustment(30.0, 0.025)
        assert result.tier == ResonanceTier.NEUTRAL
        assert result.adjustment_pct == 0.0
        assert result.adjusted_terminal_growth == 0.025
        assert result.original_terminal_growth == 0.025

    def test_clamps_at_max_terminal_growth(self) -> None:
        """Adjusted terminal growth clamped at max_terminal_growth=0.10."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        result = calculate_dcf_adjustment(90.0, 0.095, max_terminal_growth=0.10)
        # adjustment = 0.015 (STRONGLY_SUPPORTIVE)
        # 0.095 + 0.015 = 0.11, but clamped at 0.10
        assert result.tier == ResonanceTier.STRONGLY_SUPPORTIVE
        assert result.adjustment_pct == 0.015
        assert result.adjusted_terminal_growth == 0.10
        assert result.original_terminal_growth == 0.095

    def test_no_clamp_when_within_bounds(self) -> None:
        """No clamping when adjusted value is within bounds."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        result = calculate_dcf_adjustment(85.0, 0.03, max_terminal_growth=0.10)
        assert result.adjusted_terminal_growth == 0.045

    def test_custom_config(self) -> None:
        """Custom config overrides default thresholds."""
        from stockvaluefinder.services.policy_service import calculate_dcf_adjustment

        custom_config = PolicyResonanceConfig(
            STRONG_TIER_THRESHOLD=70.0,
            STRONG_ADJUSTMENT=0.02,
            MODERATE_ADJUSTMENT=0.01,
            NEUTRAL_ADJUSTMENT=0.0,
        )
        result = calculate_dcf_adjustment(75.0, 0.03, config=custom_config)
        assert result.tier == ResonanceTier.STRONGLY_SUPPORTIVE
        assert result.adjustment_pct == 0.02
        assert result.adjusted_terminal_growth == 0.05


# ---------------------------------------------------------------------------
# parse_llm_verification
# ---------------------------------------------------------------------------


class TestParseLLMVerification:
    """Tests for parse_llm_verification pure function."""

    def test_valid_json(self) -> None:
        """Valid JSON string parsed correctly."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification(
            '{"relevant": true, "confidence": 0.9, "reason": "test"}'
        )
        assert result is not None
        assert result["relevant"] is True
        assert result["confidence"] == 0.9
        assert result["reason"] == "test"

    def test_code_block_json(self) -> None:
        """JSON inside markdown code block parsed correctly."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification(
            '```json\n{"relevant": false, "confidence": 0.1, "reason": "unrelated"}\n```'
        )
        assert result is not None
        assert result["relevant"] is False
        assert result["confidence"] == 0.1
        assert result["reason"] == "unrelated"

    def test_code_block_no_language(self) -> None:
        """JSON inside code block without language tag."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification(
            '```\n{"relevant": true, "confidence": 0.8, "reason": "match"}\n```'
        )
        assert result is not None
        assert result["relevant"] is True

    def test_invalid_input(self) -> None:
        """Non-JSON input returns None."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification("not json at all")
        assert result is None

    def test_empty_input(self) -> None:
        """Empty string returns None."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification("")
        assert result is None

    def test_mixed_text_with_json(self) -> None:
        """JSON embedded in mixed text returns parsed dict."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification(
            'Here is my analysis:\n{"relevant": true, "confidence": 0.75, "reason": "partial match"}\nEnd.'
        )
        assert result is not None
        assert result["relevant"] is True
        assert result["confidence"] == 0.75

    def test_missing_required_key_relevant(self) -> None:
        """JSON missing 'relevant' key returns None."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification('{"confidence": 0.9, "reason": "test"}')
        assert result is None

    def test_missing_required_key_confidence(self) -> None:
        """JSON missing 'confidence' key returns None."""
        from stockvaluefinder.services.policy_service import parse_llm_verification

        result = parse_llm_verification('{"relevant": true, "reason": "test"}')
        assert result is None


# ---------------------------------------------------------------------------
# parse_metadata_extraction
# ---------------------------------------------------------------------------


class TestParseMetadataExtraction:
    """Tests for parse_metadata_extraction pure function."""

    def test_valid_full_json(self) -> None:
        """Valid JSON with all fields parsed correctly."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '{"title": "New Energy Policy", "policy_type": "industry", '
            '"issuing_body": "NDRC", "effective_date": "2025-01-01", '
            '"industry_tags": ["new energy", "solar"]}'
        )
        assert result is not None
        assert result["title"] == "New Energy Policy"
        assert result["policy_type"] == "industry"
        assert result["issuing_body"] == "NDRC"
        assert result["effective_date"] == "2025-01-01"
        assert result["industry_tags"] == ["new energy", "solar"]

    def test_missing_optional_effective_date(self) -> None:
        """JSON without effective_date defaults to None."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '{"title": "Policy", "policy_type": "fiscal", "issuing_body": "MOF"}'
        )
        assert result is not None
        assert result["title"] == "Policy"
        assert result.get("effective_date") is None

    def test_missing_optional_industry_tags(self) -> None:
        """JSON without industry_tags defaults to empty list."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '{"title": "Policy", "policy_type": "fiscal", "issuing_body": "MOF"}'
        )
        assert result is not None
        assert result.get("industry_tags", []) == []

    def test_code_block_wrapped(self) -> None:
        """JSON inside markdown code block parsed correctly."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '```json\n{"title": "Test", "policy_type": "trade", '
            '"issuing_body": "MOC"}\n```'
        )
        assert result is not None
        assert result["title"] == "Test"

    def test_invalid_input(self) -> None:
        """Non-JSON input returns None."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction("not json")
        assert result is None

    def test_missing_required_key_title(self) -> None:
        """JSON missing 'title' key returns None."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '{"policy_type": "fiscal", "issuing_body": "MOF"}'
        )
        assert result is None

    def test_missing_required_key_issuing_body(self) -> None:
        """JSON missing 'issuing_body' key returns None."""
        from stockvaluefinder.services.policy_service import parse_metadata_extraction

        result = parse_metadata_extraction(
            '{"title": "Policy", "policy_type": "fiscal"}'
        )
        assert result is None
