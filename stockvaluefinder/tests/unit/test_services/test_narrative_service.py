"""Tests for narrative service with mocked LLM."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.services.narrative_service import (
    NarrativeService,
    get_narrative_service,
    reset_narrative_service,
)
from stockvaluefinder.services.narrative_prompts import build_valuation_prompt


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton before and after each test."""
    reset_narrative_service()
    yield
    reset_narrative_service()


class TestParseLLMResponse:
    """Test the _parse_llm_response method."""

    def test_plain_json(self):
        svc = NarrativeService()
        content = json.dumps(
            {"summary": "测试", "key_drivers": ["a"], "risks": ["b"]},
            ensure_ascii=False,
        )
        result = svc._parse_llm_response(content)
        assert result is not None
        assert result["summary"] == "测试"
        assert result["key_drivers"] == ["a"]

    def test_markdown_code_block(self):
        svc = NarrativeService()
        content = '```json\n{"summary": "测试", "key_drivers": [], "risks": []}\n```'
        result = svc._parse_llm_response(content)
        assert result is not None
        assert result["summary"] == "测试"

    def test_empty_response(self):
        svc = NarrativeService()
        assert svc._parse_llm_response("") is None
        assert svc._parse_llm_response(None) is None

    def test_mixed_text_with_json(self):
        svc = NarrativeService()
        content = 'Here is the analysis:\n{"summary": "混合", "key_drivers": ["x"], "risks": ["y"]}'
        result = svc._parse_llm_response(content)
        assert result is not None
        assert result["summary"] == "混合"

    def test_non_json_response(self):
        svc = NarrativeService()
        assert svc._parse_llm_response("This is just plain text.") is None


class TestGenerateNarrative:
    """Test generate_narrative with mocked LLM."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.content = json.dumps(
            {
                "summary": "茅台估值偏低",
                "key_drivers": ["品牌溢价", "现金流稳定"],
                "risks": ["政策风险"],
            }
        )
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        svc = NarrativeService()
        svc._llm = mock_llm
        svc._llm_initialized = True
        svc._provider_name = "deepseek"

        result = await svc.generate_narrative(
            ticker="600519.SH",
            result_data={"intrinsic_value": 220000},
            prompt_builder=build_valuation_prompt,
        )
        assert result is not None
        assert result.summary == "茅台估值偏低"
        assert result.key_drivers == ["品牌溢价", "现金流稳定"]
        assert result.risks == ["政策风险"]
        assert result.llm_provider == "deepseek"
        assert isinstance(result.generated_at, datetime)

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_none(self):
        svc = NarrativeService()
        svc._llm = None
        svc._llm_initialized = True

        result = await svc.generate_narrative(
            ticker="600519.SH",
            result_data={"price": 100},
            prompt_builder=build_valuation_prompt,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_unparseable(self):
        svc = NarrativeService()
        mock_response = MagicMock()
        mock_response.content = "I cannot answer this question."
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        svc._llm = mock_llm
        svc._llm_initialized = True
        svc._provider_name = "deepseek"

        result = await svc.generate_narrative(
            ticker="600519.SH",
            result_data={"price": 100},
            prompt_builder=build_valuation_prompt,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        svc = NarrativeService()
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=ValueError("Missing API key"))
        svc._llm = mock_llm
        svc._llm_initialized = True
        svc._provider_name = "deepseek"

        result = await svc.generate_narrative(
            ticker="600519.SH",
            result_data={"price": 100},
            prompt_builder=build_valuation_prompt,
        )
        assert result is None


class TestGetNarrativeService:
    """Test singleton behavior."""

    def test_returns_singleton(self):
        svc1 = get_narrative_service()
        svc2 = get_narrative_service()
        assert svc1 is svc2

    def test_reset_creates_new(self):
        get_narrative_service()
        reset_narrative_service()
        svc = get_narrative_service()
        assert isinstance(svc, NarrativeService)
