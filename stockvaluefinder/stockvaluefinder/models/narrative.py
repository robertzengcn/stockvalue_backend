"""Pydantic models for LLM-generated analysis narratives."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.models.valuation import ValuationResult
from stockvaluefinder.models.yield_gap import YieldGap
from stockvaluefinder.services.narrative_prompts import PromptBuilder


class AnalysisNarrative(BaseModel):
    """LLM-generated narrative explanation for an analysis result."""

    model_config = {"frozen": True}

    summary: str = Field(
        ..., max_length=500, description="Summary of analysis in Chinese"
    )
    key_drivers: list[str] = Field(
        default_factory=list, max_length=3, description="Key drivers identified by LLM"
    )
    risks: list[str] = Field(
        default_factory=list, max_length=3, description="Risk factors identified by LLM"
    )
    generated_at: datetime = Field(
        ..., description="Timestamp when narrative was generated"
    )
    llm_provider: str = Field(..., description="LLM provider used (e.g. 'deepseek')")


class DCFExplanation(BaseModel):
    """AI-generated step-by-step DCF calculation explanation."""

    model_config = {"frozen": True}

    step_by_step: str = Field(..., description="Step-by-step calculation walkthrough")
    data_inputs: str = Field(..., description="Description of input data used")
    wacc_explanation: str = Field(..., description="How WACC was derived")
    fcf_analysis: str = Field(
        ..., description="FCF projection methodology and assessment"
    )
    reliability: str = Field(
        ..., description="Assessment of result reliability and caveats"
    )
    conclusion: str = Field(..., description="Summary of the valuation conclusion")
    generated_at: datetime = Field(
        ..., description="Timestamp when explanation was generated"
    )
    llm_provider: str = Field(..., description="LLM provider used (e.g. 'deepseek')")


class ValuationResultWithNarrative(ValuationResult):
    """Valuation result with optional LLM narrative."""

    stock_name: str | None = Field(None, description="Stock name (e.g., '贵州茅台')")
    narrative: AnalysisNarrative | None = Field(
        None, description="LLM-generated narrative (null if LLM unavailable)"
    )


class RiskScoreWithNarrative(RiskScore):
    """Risk score with optional LLM narrative."""

    narrative: AnalysisNarrative | None = Field(
        None, description="LLM-generated narrative (null if LLM unavailable)"
    )


class YieldGapWithNarrative(YieldGap):
    """Yield gap result with optional LLM narrative."""

    narrative: AnalysisNarrative | None = Field(
        None, description="LLM-generated narrative (null if LLM unavailable)"
    )


def wrap_with_narrative(
    result: ValuationResult | RiskScore | YieldGap,
    narrative: AnalysisNarrative | None,
) -> ValuationResultWithNarrative | RiskScoreWithNarrative | YieldGapWithNarrative:
    """Wrap a result model with an optional narrative.

    Returns the appropriate *WithNarrative type based on the input type.
    """
    data = result.model_dump()

    if isinstance(result, ValuationResult):
        return ValuationResultWithNarrative(**data, narrative=narrative)
    if isinstance(result, RiskScore):
        return RiskScoreWithNarrative(**data, narrative=narrative)
    if isinstance(result, YieldGap):
        return YieldGapWithNarrative(**data, narrative=narrative)

    raise TypeError(f"Unsupported result type: {type(result)}")


async def generate_and_serialize_narrative(
    ticker: str,
    result_data: dict[str, Any],
    prompt_builder: PromptBuilder,
    narrative_svc: Any,
) -> tuple[AnalysisNarrative | None, str | None]:
    """Generate an LLM narrative and serialize it for persistence.

    Shared helper used by all three analysis routes to avoid duplicating
    the narrative generation + JSON serialization logic.

    Args:
        ticker: Stock code
        result_data: Analysis result as dict (from model_dump())
        prompt_builder: Function that builds (system, user) prompt tuple
        narrative_svc: NarrativeService instance

    Returns:
        Tuple of (narrative object for API response, narrative JSON for DB)
    """
    narrative = await narrative_svc.generate_narrative(
        ticker=ticker,
        result_data=result_data,
        prompt_builder=prompt_builder,
    )

    narrative_json: str | None = None
    if narrative is not None:
        narrative_json = json.dumps(
            narrative.model_dump(), ensure_ascii=False, default=str
        )

    return narrative, narrative_json
