"""Risk analysis API endpoints."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.stock_helpers import (
    ensure_financial_report_exists,
    ensure_stock_exists,
)
from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.narrative import (
    RiskScoreWithNarrative,
    generate_and_serialize_narrative,
)
from stockvaluefinder.models.risk import RiskScoreCreate
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.retriever import SemanticRetriever, SearchResult
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.repositories.risk_repo import RiskScoreRepository
from stockvaluefinder.services.narrative_prompts import build_risk_prompt
from stockvaluefinder.services.narrative_service import get_narrative_service
from stockvaluefinder.services.risk_service import RiskAnalyzer
from stockvaluefinder.utils.errors import DataValidationError, ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analyze/risk", tags=["risk"])


async def _fetch_document_context(
    document_ids: list[str],
    ticker: str,
    year: int | None = None,
) -> list[SearchResult]:
    """Fetch document context from Qdrant for the given document IDs.

    Searches across the specified documents using the ticker as the query
    to find relevant passages. Returns empty list on failure (graceful
    degradation).

    Args:
        document_ids: List of document UUIDs to search within.
        ticker: Stock ticker used as the search query.
        year: Optional year filter.

    Returns:
        List of SearchResult objects, or empty list on failure.
    """
    try:
        embedding_client = BGEEmbeddingClient()
        vector_store = QdrantVectorStore(
            url=rag_config.QDRANT_URL,
            collection=rag_config.QDRANT_COLLECTION,
            api_key=rag_config.QDRANT_API_KEY,
            embedding_client=embedding_client,
        )
        retriever = SemanticRetriever(
            vector_store=vector_store,
            embedding_client=embedding_client,
        )
        return await retriever.search(
            query=ticker,
            ticker=ticker,
            year=year,
            limit=10,
            score_threshold=0.5,
        )
    except Exception:
        logger.warning(
            "Failed to fetch document context for %s (docs: %s)",
            ticker,
            document_ids,
            exc_info=True,
        )
        return []


class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    year: int | None = Field(
        None,
        ge=2000,
        le=2099,
        description="Fiscal year for analysis (defaults to most recent)",
    )
    document_ids: list[str] | None = Field(
        None,
        description="Optional document IDs to retrieve RAG context for analysis",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "0700.HK", "year": 2023},
                {"ticker": "000002.SZ"},
                {
                    "ticker": "600519.SH",
                    "document_ids": ["doc-uuid-1", "doc-uuid-2"],
                },
            ]
        }


@router.post("/", response_model=ApiResponse[RiskScoreWithNarrative])
async def analyze_risk(
    request: RiskAnalysisRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RiskScoreWithNarrative]:
    """Analyze financial risk for a given stock."""
    try:
        ticker = request.ticker.upper()
        current_year = request.year
        current_year_param = current_year if current_year else None

        current_report = await data_service.get_financial_report(
            ticker, current_year_param
        )

        previous_year = (
            current_report["fiscal_year"] - 1
            if current_year is None
            else current_year - 1
        )
        previous_report = await data_service.get_financial_report(ticker, previous_year)

        analyzer = RiskAnalyzer()
        risk_score = analyzer.analyze(current_report, previous_report)

        # Generate LLM narrative (graceful fallback to None on failure)
        narrative_svc = get_narrative_service()
        narrative, narrative_json = await generate_and_serialize_narrative(
            ticker=ticker,
            result_data=risk_score.model_dump(),
            prompt_builder=build_risk_prompt,
            narrative_svc=narrative_svc,
        )

        # Save to database with explicit transaction handling
        try:
            market = Market.HK_SHARE if ticker.endswith(".HK") else Market.A_SHARE
            await ensure_stock_exists(ticker, market, data_service, db)
            report_id = await ensure_financial_report_exists(current_report, db)

            risk_repo = RiskScoreRepository(db)

            risk_create = RiskScoreCreate(
                score_id=uuid4(),
                ticker=risk_score.ticker,
                report_id=report_id,
                risk_level=risk_score.risk_level,
                m_score=risk_score.m_score,
                mscore_data=risk_score.mscore_data,
                f_score=risk_score.f_score,
                fscore_data=risk_score.fscore_data,
                存贷双高=risk_score.存贷双高,
                cash_amount=risk_score.cash_amount,
                debt_amount=risk_score.debt_amount,
                cash_growth_rate=risk_score.cash_growth_rate,
                debt_growth_rate=risk_score.debt_growth_rate,
                goodwill_ratio=risk_score.goodwill_ratio,
                goodwill_excessive=risk_score.goodwill_excessive,
                profit_cash_divergence=risk_score.profit_cash_divergence,
                profit_growth=risk_score.profit_growth,
                ocf_growth=risk_score.ocf_growth,
                red_flags=risk_score.red_flags,
                narrative=narrative_json,
            )
            await risk_repo.upsert_by_report_id(risk_create)
            await db.commit()
            logger.info(f"Successfully saved risk analysis for {ticker} to database")
        except Exception as db_error:
            await db.rollback()
            logger.error(f"Failed to save risk analysis for {ticker}: {db_error}")

        result = RiskScoreWithNarrative(**risk_score.model_dump(), narrative=narrative)

        # Fetch document context if document_ids provided (graceful degradation)
        doc_context: list[dict[str, object]] | None = None
        if request.document_ids:
            search_results = await _fetch_document_context(
                document_ids=request.document_ids,
                ticker=ticker,
                year=request.year,
            )
            doc_context = [
                {
                    "chunk_id": r.chunk_id,
                    "content": r.content,
                    "parent_content": r.parent_content,
                    "page_number": r.page_number,
                    "section": r.section,
                    "score": r.score,
                }
                for r in search_results
            ]

        return ApiResponse(
            success=True,
            data=result,
            meta={"document_context": doc_context} if doc_context else None,
        )

    except DataValidationError as e:
        logger.warning(f"Data validation error for {request.ticker}: {e}")
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        logger.error(f"External API error for {request.ticker}: {e}")
        return ApiResponse(
            success=False,
            error="Failed to fetch financial data. Please try again later.",
        )
    except Exception:
        logger.exception(f"Unexpected error in risk analysis for {request.ticker}")
        return ApiResponse(
            success=False, error="An internal error occurred. Please try again later."
        )
