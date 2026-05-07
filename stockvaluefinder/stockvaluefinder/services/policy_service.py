"""Policy resonance calculation service - pure functions for policy-stock matching.

This module provides pure functions for calculating policy resonance scores,
classifying resonance tiers, computing DCF terminal growth adjustments, and
parsing LLM structured output for match verification and metadata extraction.

Key formulas (D-04):
    - Resonance Score = 60% * (avg_cosine * 100) + 40% * (avg_confidence * 100)
    - Only verified-relevant matches (LLM relevant=True) contribute
    - Zero relevant matches -> score = 0.0 (not NaN)

DCF Adjustment (D-07):
    - Strongly Supportive (>=80): +1.5%
    - Supportive (40-79): +1.0%
    - Neutral (<40): 0%

Clamping (D-08):
    - Hard cap at +1.5% adjustment
    - Subject to ValuationConfig.MAX_TERMINAL_GROWTH absolute cap

All functions are stateless pure functions with no I/O side effects.
"""

import json
import re
from typing import Any

from stockvaluefinder.config import PolicyResonanceConfig, policy_resonance_config
from stockvaluefinder.models.enums import ResonanceTier
from stockvaluefinder.models.policy import DCFAdjustment


def calculate_resonance_score(
    verified_matches: list[dict[str, Any]],
    config: PolicyResonanceConfig | None = None,
) -> float:
    """Calculate policy resonance score per D-04.

    Weighted formula: COSINE_WEIGHT * (avg_cosine * 100) + LLM_WEIGHT * (avg_confidence * 100).
    Only relevant=True matches contribute to the score.

    Args:
        verified_matches: List of dicts with 'score', 'relevant', 'confidence' keys.
            Each dict represents a policy chunk match with LLM verification.
        config: PolicyResonanceConfig. Falls back to global instance if None.

    Returns:
        Resonance score 0.0-100.0. Returns 0.0 if no relevant matches.

    Examples:
        >>> calculate_resonance_score([
        ...     {"score": 0.85, "relevant": True, "confidence": 0.9, "reason": "..."},
        ...     {"score": 0.75, "relevant": True, "confidence": 0.8, "reason": "..."},
        ... ])
        82.0
        >>> calculate_resonance_score([
        ...     {"score": 0.85, "relevant": False, "confidence": 0.1, "reason": "..."},
        ... ])
        0.0
        >>> calculate_resonance_score([])
        0.0
    """
    if config is None:
        config = policy_resonance_config

    relevant = [m for m in verified_matches if m.get("relevant") is True]
    if not relevant:
        return 0.0

    avg_cosine = sum(m["score"] for m in relevant) / len(relevant)
    avg_confidence = sum(m["confidence"] for m in relevant) / len(relevant)

    score = config.COSINE_WEIGHT * (avg_cosine * 100) + config.LLM_WEIGHT * (
        avg_confidence * 100
    )
    return round(max(0.0, min(100.0, score)), 2)


def classify_resonance_tier(
    score: float,
    config: PolicyResonanceConfig | None = None,
) -> ResonanceTier:
    """Classify resonance score into tier per D-07.

    Tier thresholds:
        - >= STRONG_TIER_THRESHOLD (80.0): STRONGLY_SUPPORTIVE
        - >= RESONANCE_THRESHOLD (40.0): SUPPORTIVE
        - < RESONANCE_THRESHOLD: NEUTRAL

    Args:
        score: Resonance score (0-100).
        config: PolicyResonanceConfig. Falls back to global instance if None.

    Returns:
        ResonanceTier enum value.

    Examples:
        >>> classify_resonance_tier(85.0)
        <ResonanceTier.STRONGLY_SUPPORTIVE: 'strongly_supportive'>
        >>> classify_resonance_tier(60.0)
        <ResonanceTier.SUPPORTIVE: 'supportive'>
        >>> classify_resonance_tier(30.0)
        <ResonanceTier.NEUTRAL: 'neutral'>
    """
    if config is None:
        config = policy_resonance_config

    if score >= config.STRONG_TIER_THRESHOLD:
        return ResonanceTier.STRONGLY_SUPPORTIVE
    elif score >= config.RESONANCE_THRESHOLD:
        return ResonanceTier.SUPPORTIVE
    else:
        return ResonanceTier.NEUTRAL


def calculate_dcf_adjustment(
    resonance_score: float,
    original_terminal_growth: float,
    max_terminal_growth: float = 0.10,
    config: PolicyResonanceConfig | None = None,
) -> DCFAdjustment:
    """Calculate DCF terminal growth adjustment per D-07 and D-08.

    Determines tier-based adjustment and clamps the adjusted terminal growth
    at max_terminal_growth (ValuationConfig.MAX_TERMINAL_GROWTH).

    Args:
        resonance_score: 0-100 score from calculate_resonance_score().
        original_terminal_growth: Current terminal growth rate (e.g., 0.025).
        max_terminal_growth: Absolute cap from ValuationConfig (default 0.10).
        config: PolicyResonanceConfig. Falls back to global instance if None.

    Returns:
        DCFAdjustment with tier, adjustment_pct, adjusted_terminal_growth,
        and original_terminal_growth.

    Examples:
        >>> calculate_dcf_adjustment(85.0, 0.025).adjusted_terminal_growth
        0.04
        >>> calculate_dcf_adjustment(30.0, 0.025).adjustment_pct
        0.0
        >>> calculate_dcf_adjustment(90.0, 0.095, max_terminal_growth=0.10).adjusted_terminal_growth
        0.1
    """
    if config is None:
        config = policy_resonance_config

    tier = classify_resonance_tier(resonance_score, config)

    if tier == ResonanceTier.STRONGLY_SUPPORTIVE:
        adjustment = config.STRONG_ADJUSTMENT
    elif tier == ResonanceTier.SUPPORTIVE:
        adjustment = config.MODERATE_ADJUSTMENT
    else:
        adjustment = config.NEUTRAL_ADJUSTMENT

    # D-08: Clamp adjusted terminal growth at max_terminal_growth
    adjusted = min(original_terminal_growth + adjustment, max_terminal_growth)

    return DCFAdjustment(
        tier=tier,
        adjustment_pct=adjustment,
        adjusted_terminal_growth=round(adjusted, 6),
        original_terminal_growth=original_terminal_growth,
    )


def _safe_json_parse(text: str) -> dict[str, Any] | None:
    """Safely parse JSON string, returning None on failure.

    Args:
        text: JSON string to parse.

    Returns:
        Parsed dict or None.
    """
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_json_from_content(content: str) -> dict[str, Any] | None:
    """Extract JSON dict from LLM response content.

    Handles three formats:
    1. JSON inside markdown code blocks (```json ... ```)
    2. Plain JSON string
    3. Mixed text with embedded JSON object

    Args:
        content: Raw LLM response string.

    Returns:
        Parsed dict or None if no valid JSON found.
    """
    if not content or not content.strip():
        return None

    # 1. Try extracting from markdown code blocks
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(code_block_pattern, content, re.DOTALL)
    if match:
        result = _safe_json_parse(match.group(1).strip())
        if result is not None:
            return result

    # 2. Try parsing whole content as JSON
    result = _safe_json_parse(content.strip())
    if result is not None:
        return result

    # 3. Try finding JSON object in mixed text
    brace_pattern = r"\{[^{}]*\}"
    match = re.search(brace_pattern, content, re.DOTALL)
    if match:
        return _safe_json_parse(match.group(0))

    return None


def parse_llm_verification(content: str) -> dict[str, Any] | None:
    """Parse LLM match verification response per D-05.

    Extracts structured verdict from LLM output: {relevant, confidence, reason}.
    Validates that required keys (relevant, confidence) are present.

    Args:
        content: Raw LLM response string.

    Returns:
        Parsed dict with 'relevant' (bool) and 'confidence' (float) keys,
        or None if parsing fails or required keys are missing.

    Examples:
        >>> parse_llm_verification('{"relevant": true, "confidence": 0.9, "reason": "test"}')
        {'relevant': True, 'confidence': 0.9, 'reason': 'test'}
        >>> parse_llm_verification('not json') is None
        True
    """
    parsed = _extract_json_from_content(content)
    if parsed is None:
        return None

    # Validate required keys (T-11-01 mitigation)
    if "relevant" not in parsed or "confidence" not in parsed:
        return None

    # Type validation
    if not isinstance(parsed["relevant"], bool):
        return None
    if not isinstance(parsed["confidence"], (int, float)):
        return None
    # Clamp confidence to [0.0, 1.0] range
    parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))

    return parsed


def parse_metadata_extraction(content: str) -> dict[str, Any] | None:
    """Parse LLM metadata extraction response per D-10.

    Extracts structured metadata from policy document content:
    {title, policy_type, issuing_body, effective_date, industry_tags}.

    Validates required keys (title, policy_type, issuing_body).
    Defaults optional fields: effective_date -> None, industry_tags -> [].

    Args:
        content: Raw LLM response string.

    Returns:
        Parsed dict with all metadata fields, or None if parsing fails
        or required keys are missing.

    Examples:
        >>> r = parse_metadata_extraction(
        ...     '{"title": "Policy", "policy_type": "fiscal", "issuing_body": "MOF"}'
        ... )
        >>> r is not None
        True
        >>> r["title"]
        'Policy'
        >>> r.get("effective_date") is None
        True
    """
    parsed = _extract_json_from_content(content)
    if parsed is None:
        return None

    # Validate required keys (T-11-02 mitigation)
    required_keys = ("title", "policy_type", "issuing_body")
    for key in required_keys:
        if key not in parsed:
            return None

    # Default optional fields (new dict to avoid mutation)
    result = {
        "title": parsed["title"],
        "policy_type": parsed["policy_type"],
        "issuing_body": parsed["issuing_body"],
        "effective_date": parsed.get("effective_date"),
        "industry_tags": parsed.get("industry_tags", []),
    }

    return result
