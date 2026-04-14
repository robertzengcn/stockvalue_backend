"""Narrative generation service using LLM with graceful fallback.

This service wraps LLM calls for generating Chinese narrative explanations
of analysis results. If the LLM is unavailable for any reason, it returns
None -- the calling route never fails due to narrative generation.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from stockvaluefinder.models.narrative import AnalysisNarrative, DCFExplanation
from stockvaluefinder.services.narrative_prompts import (
    PromptBuilder,
    build_dcf_explanation_prompt,
)

logger = logging.getLogger(__name__)


class NarrativeService:
    """Service for generating LLM narratives with graceful fallback."""

    def __init__(self) -> None:
        """Initialize with lazy LLM client."""
        self._llm: Any = None
        self._llm_initialized = False
        self._provider_name: str = ""

    def _get_llm(self) -> Any:
        """Lazily initialize and return the LLM client.

        Returns None if initialization fails (missing API key, etc.)
        """
        if not self._llm_initialized:
            try:
                from stockvaluefinder.llm_factory import create_llm

                self._llm = create_llm(provider="deepseek")
                self._provider_name = "deepseek"
                self._llm_initialized = True
            except Exception:
                logger.warning(
                    "LLM initialization failed; narratives will be disabled",
                    exc_info=True,
                )
                self._llm = None
                self._llm_initialized = True
        return self._llm

    async def generate_narrative(
        self,
        ticker: str,
        result_data: dict[str, Any],
        prompt_builder: PromptBuilder,
    ) -> AnalysisNarrative | None:
        """Generate an LLM narrative for an analysis result.

        Args:
            ticker: Stock code
            result_data: Analysis result as dict (from model_dump())
            prompt_builder: Function that builds (system, user) prompt tuple

        Returns:
            AnalysisNarrative if LLM succeeds, None on any failure
        """
        try:
            llm = self._get_llm()
            if llm is None:
                return None

            system_prompt, user_prompt = prompt_builder(ticker, result_data)

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await llm.ainvoke(messages)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            parsed = self._parse_llm_response(content)
            if parsed is None:
                logger.warning(f"Failed to parse LLM response for {ticker} narrative")
                return None

            return AnalysisNarrative(
                summary=parsed.get("summary", ""),
                key_drivers=parsed.get("key_drivers", []),
                risks=parsed.get("risks", []),
                generated_at=datetime.now(tz=timezone.utc),
                llm_provider=self._provider_name,
            )

        except Exception:
            logger.warning(
                f"Narrative generation failed for {ticker}",
                exc_info=True,
            )
            return None

    async def generate_dcf_explanation(
        self,
        ticker: str,
        result_data: dict[str, Any],
    ) -> DCFExplanation | None:
        """Generate a step-by-step DCF explanation via LLM.

        Args:
            ticker: Stock code
            result_data: Valuation result dict including audit_trail

        Returns:
            DCFExplanation if LLM succeeds, None on any failure
        """
        try:
            llm = self._get_llm()
            if llm is None:
                return None

            system_prompt, user_prompt = build_dcf_explanation_prompt(
                ticker, result_data
            )

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await llm.ainvoke(messages)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            parsed = self._parse_llm_response(content)
            if parsed is None:
                logger.warning(
                    f"Failed to parse LLM response for {ticker} DCF explanation"
                )
                return None

            return DCFExplanation(
                step_by_step=parsed.get("step_by_step", ""),
                data_inputs=parsed.get("data_inputs", ""),
                wacc_explanation=parsed.get("wacc_explanation", ""),
                fcf_analysis=parsed.get("fcf_analysis", ""),
                reliability=parsed.get("reliability", ""),
                conclusion=parsed.get("conclusion", ""),
                generated_at=datetime.now(tz=timezone.utc),
                llm_provider=self._provider_name,
            )

        except Exception:
            logger.warning(
                f"DCF explanation generation failed for {ticker}",
                exc_info=True,
            )
            return None

    def _parse_llm_response(self, content: str) -> dict[str, Any] | None:
        """Parse LLM response content into a dict.

        Handles three formats:
        1. Plain JSON
        2. JSON inside markdown code blocks (```json ... ```)
        3. Mixed text with embedded JSON

        Args:
            content: Raw LLM response string

        Returns:
            Parsed dict or None if parsing fails
        """
        if not content or not content.strip():
            return None

        # Try extracting JSON from markdown code blocks first
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(code_block_pattern, content, re.DOTALL)
        if match:
            return self._safe_json_parse(match.group(1).strip())

        # Try parsing the whole content as JSON
        result = self._safe_json_parse(content.strip())
        if result is not None:
            return result

        # Try to find JSON object in mixed text
        brace_pattern = r"\{[^{}]*\}"
        match = re.search(brace_pattern, content, re.DOTALL)
        if match:
            return self._safe_json_parse(match.group(0))

        return None

    @staticmethod
    def _safe_json_parse(text: str) -> dict[str, Any] | None:
        """Safely parse JSON string, returning None on failure."""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return None
        except (json.JSONDecodeError, TypeError):
            return None


# Module-level singleton
_narrative_service: NarrativeService | None = None


def get_narrative_service() -> NarrativeService:
    """Get or create the module-level NarrativeService singleton."""
    global _narrative_service
    if _narrative_service is None:
        _narrative_service = NarrativeService()
    return _narrative_service


def reset_narrative_service() -> None:
    """Reset the singleton (for testing)."""
    global _narrative_service
    _narrative_service = None
