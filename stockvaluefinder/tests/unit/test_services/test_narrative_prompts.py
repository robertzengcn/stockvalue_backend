"""Tests for narrative prompt builder functions."""


from stockvaluefinder.services.narrative_prompts import (
    SYSTEM_PROMPT,
    PromptBuilder,
    build_risk_prompt,
    build_valuation_prompt,
    build_yield_prompt,
)


class TestSystemPrompt:
    """Test that the system prompt is well-defined."""

    def test_contains_role_definition(self):
        assert "价值投资分析师" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT
        assert "中文" in SYSTEM_PROMPT
        assert "summary" in SYSTEM_PROMPT
        assert "key_drivers" in SYSTEM_PROMPT
        assert "risks" in SYSTEM_PROMPT


class TestPromptBuilderType:
    """Test PromptBuilder type alias."""

    def test_type_exists(self):
        assert PromptBuilder is not None


class TestBuildValuationPrompt:
    """Test valuation prompt builds correctly."""

    def test_basic_build(self):
        ticker = "600519.SH"
        data = {"current_price": 1800.50, "intrinsic_value": 220000.0, "wacc": 0.2}
        system_prompt, user_prompt = build_valuation_prompt(ticker, data)
        assert system_prompt == SYSTEM_PROMPT
        assert ticker in user_prompt
        assert "DCF" in user_prompt
        assert "1800" in user_prompt
        assert "安全边际" in user_prompt
        assert "WACC" in user_prompt

    def test_chinese_data_serialization(self):
        """Test that Chinese data is properly serialized."""
        data = {"valuation_level": "低估", "margin_of_safety": 0.35}
        _system, user = build_valuation_prompt("600519.SH", data)
        assert "低估" in user
        assert "0.35" in user


class TestBuildRiskPrompt:
    """Test risk prompt builds correctly."""

    def test_basic_build(self):
        ticker = "0700.HK"
        data = {"risk_level": "HIGH", "m_score": -1.5}
        system_prompt, user_prompt = build_risk_prompt(ticker, data)
        assert system_prompt == SYSTEM_PROMPT
        assert "0700.HK" in user_prompt
        assert "M-Score" in user_prompt
        assert "存贷双高" in user_prompt
        assert "商誉" in user_prompt

    def test_chinese_data_serialization(self):
        """Test that Chinese data is properly serialized."""
        data = {"风险等级": "高", "m_score": -1.5}
        _, user = build_risk_prompt("600519.SH", data)
        assert "高" in user
        assert "-1.5" in user


class TestBuildYieldPrompt:
    """Test yield prompt builds correctly."""

    def test_basic_build(self):
        ticker = "600519.SH"
        data = {"yield_gap": 0.02, "recommendation": "ATTRACTIVE"}
        system_prompt, user_prompt = build_yield_prompt(ticker, data)
        assert system_prompt == SYSTEM_PROMPT
        assert ticker in user_prompt
        assert "股息收益率" in user_prompt
        assert "yield_gap" in user_prompt
        assert "国债" in user_prompt
        assert "存单" in user_prompt

    def test_chinese_data_serialization(self):
        """Test that Chinese data is properly serialized."""
        data = {"recommendation": "有吸引力", "yield_gap": 0.02}
        _, user = build_yield_prompt("600519.SH", data)
        assert "有吸引力" in user
        assert "0.02" in user
