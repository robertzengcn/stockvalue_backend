"""Tests for narrative prompt builder functions."""

import re

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


class TestBuildRiskPromptPledgeSection:
    """Test pledge risk section in build_risk_prompt."""

    def test_backward_compatible_no_pledge_data(self):
        """NARR: Calling without pledge_data produces no pledge section."""
        _, user = build_risk_prompt("600519.SH", {"risk_level": "LOW"})
        assert "质押" not in user

    def test_hk_stock_unsupported(self):
        """HK stocks get simple note, no risk assessment."""
        pledge_data = {
            "supported": False,
            "data_quality": {"freshness": "UNAVAILABLE"},
        }
        _, user = build_risk_prompt("600519.SH", {}, pledge_data=pledge_data)
        assert "港股" in user
        assert "不支持质押数据" in user
        # Should NOT contain pledge risk analysis details (risk_level_breakdown, etc.)
        assert "最终风险等级" not in user
        assert "公司质押比例" not in user

    def test_unavailable_freshness_guardrail(self):
        """NARR-03: Unavailable data must state 'data unavailable', forbid risk inference."""
        pledge_data = {
            "supported": True,
            "data_quality": {"freshness": "UNAVAILABLE"},
        }
        _, user = build_risk_prompt("600519.SH", {}, pledge_data=pledge_data)
        assert "不可得" in user
        assert "不得暗示" in user
        assert "不得对质押风险做出任何推断" in user

    def test_full_pledge_data_with_guardrails(self):
        """NARR-01: Full pledge section with structured data and NARR-02 guardrails."""
        pledge_data = {
            "supported": True,
            "data_quality": {"freshness": "CURRENT"},
            "company_risk": {"company_pledge_ratio": 25.0},
            "holder_risk": {"pledged_to_holding_ratio": 60.0},
            "closeout_risk": {"safety_margin": 35.0},
            "risk_level_breakdown": {"final_risk_level": "HIGH"},
        }
        _, user = build_risk_prompt("600519.SH", {}, pledge_data=pledge_data)
        # NARR-01: data values present
        assert "HIGH" in user
        assert "25.0" in user
        assert "60.0" in user
        assert "35.0" in user
        # NARR-02: guardrail text present
        assert "不得编造" in user

    def test_null_safety_margin_omits_closeout_distance(self):
        """NARR-04: When safety_margin is None, no closeout distance value emitted."""
        pledge_data = {
            "supported": True,
            "data_quality": {"freshness": "CURRENT"},
            "company_risk": {"company_pledge_ratio": 10.0},
            "holder_risk": {"pledged_to_holding_ratio": 30.0},
            "closeout_risk": {"safety_margin": None},
            "risk_level_breakdown": {"final_risk_level": "LOW"},
        }
        _, user = build_risk_prompt("600519.SH", {}, pledge_data=pledge_data)
        # Should NOT contain a closeout distance value line
        value_pattern = re.search(r"平仓线安全距离:\s*\d+\.?\d*%", user)
        assert value_pattern is None, (
            f"NARR-04 violated: found closeout distance value: {value_pattern.group()}"
        )

    def test_stale_freshness_shows_full_section(self):
        """STALE freshness still shows full pledge data section."""
        pledge_data = {
            "supported": True,
            "data_quality": {"freshness": "STALE"},
            "company_risk": {"company_pledge_ratio": 15.0},
            "holder_risk": {"pledged_to_holding_ratio": 40.0},
            "closeout_risk": {"safety_margin": 45.0},
            "risk_level_breakdown": {"final_risk_level": "MEDIUM"},
        }
        _, user = build_risk_prompt("600519.SH", {}, pledge_data=pledge_data)
        assert "MEDIUM" in user
        assert "15.0" in user
        assert "不得编造" in user
