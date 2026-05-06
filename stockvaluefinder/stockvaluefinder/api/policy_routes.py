"""Policy Resonance Engine API endpoints.

Provides endpoints for uploading policy PDF documents (chunking, embedding,
storing in Qdrant policy_documents collection) and performing resonance
analysis (semantic matching of policy text against stock business descriptions
with LLM verification and DCF terminal growth adjustment).

Endpoints:
    POST /api/v1/analyze/policy/upload    - Upload and process a policy PDF
    POST /api/v1/analyze/policy/resonance - Analyze policy resonance for a stock
"""

import logging
import os
import re
from datetime import datetime, timezone
from dataclasses import replace
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_initialized_data_service
from stockvaluefinder.api.stock_helpers import ensure_stock_exists
from stockvaluefinder.config import (
    rag_config,
    policy_resonance_config,
)
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.llm_factory import create_llm
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.document import DocumentChunk
from stockvaluefinder.models.enums import Market, ResonanceTier
from stockvaluefinder.models.policy import (
    DCFAdjustment,
    PolicyDocumentCreate,
    PolicyMatch,
    PolicyUploadResponse,
    ResonanceRequest,
    ResonanceResult,
)
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.pdf_processor import (
    chunk_into_parents,
    chunk_parents_into_children,
    extract_pdf_content,
)
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.repositories.policy_repo import PolicyDocumentRepository
from stockvaluefinder.services.policy_service import (
    calculate_dcf_adjustment,
    calculate_resonance_score,
    parse_llm_verification,
    parse_metadata_extraction,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analyze/policy", tags=["policy"])

# Maximum content length sent to LLM for metadata extraction
_METADATA_CONTENT_LIMIT = 2000


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing path traversal characters.

    Strips directory components and removes characters that could
    be used for path traversal attacks (T-11-07 mitigation).

    Args:
        filename: Original filename to sanitize.

    Returns:
        Sanitized filename with only safe characters retained.
    """
    safe_name = filename.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^\w.\-]", "_", safe_name)
    return safe_name


class PolicyLLMHelper:
    """Lazy-initialized LLM helper for policy metadata extraction and match verification.

    Follows NarrativeService pattern: returns None on any failure,
    never crashes the calling code.
    """

    def __init__(self) -> None:
        """Initialize with lazy LLM client."""
        self._llm: Any = None
        self._llm_initialized = False

    def _get_llm(self) -> Any:
        """Lazily initialize and return the LLM client.

        Returns None if initialization fails (missing API key, etc.).
        """
        if not self._llm_initialized:
            try:
                self._llm = create_llm(provider="deepseek")
                self._llm_initialized = True
            except Exception:
                logger.warning(
                    "LLM initialization failed for PolicyLLMHelper; "
                    "metadata extraction and match verification will be disabled",
                    exc_info=True,
                )
                self._llm = None
                self._llm_initialized = True
        return self._llm

    async def extract_metadata(self, content: str) -> dict[str, Any] | None:
        """Extract structured metadata from policy document content via LLM (D-10).

        Sends first ~2000 chars of content to DeepSeek for extraction of:
        title, policy_type, issuing_body, effective_date, industry_tags.

        Args:
            content: Policy document text content.

        Returns:
            Parsed metadata dict or None on failure.
        """
        try:
            llm = self._get_llm()
            if llm is None:
                return None

            truncated = content[:_METADATA_CONTENT_LIMIT]
            prompt = (
                "Extract structured metadata from this Chinese government policy document. "
                "Return a JSON object with these fields:\n"
                '- "title": The document title (string)\n'
                '- "policy_type": One of "industry", "fiscal", "monetary", "trade" '
                "(string)\n"
                '- "issuing_body": The government body that issued the policy '
                '(string, e.g. "国务院", "证监会", "发改委")\n'
                '- "effective_date": Effective date in ISO format, or null if not found\n'
                '- "industry_tags": Array of relevant industry tags (string[])\n\n'
                f"Policy content:\n{truncated}"
            )

            from langchain_core.messages import HumanMessage

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content if hasattr(response, "content") else str(response)

            return parse_metadata_extraction(text)

        except Exception:
            logger.warning("LLM metadata extraction failed", exc_info=True)
            return None

    async def verify_match(
        self, business_description: str, policy_chunk: str
    ) -> dict[str, Any] | None:
        """Verify a policy-stock match via LLM classification (D-03, D-05).

        Sends the stock's business description and a policy chunk to DeepSeek
        for relevance verification.

        Args:
            business_description: Stock's business description text.
            policy_chunk: Matched policy document chunk text.

        Returns:
            Dict with 'relevant' (bool), 'confidence' (float 0-1),
            'reason' (str), or None on LLM failure.
        """
        try:
            llm = self._get_llm()
            if llm is None:
                return None

            prompt = (
                "You are verifying whether a government policy document chunk is "
                "relevant to a company's business operations.\n\n"
                f"Company business description:\n{business_description}\n\n"
                f"Policy document chunk:\n{policy_chunk}\n\n"
                "Determine if this policy is relevant to the company's business. "
                "Return a JSON object:\n"
                '- "relevant": true or false (boolean)\n'
                '- "confidence": float between 0.0 and 1.0 indicating your '
                "confidence\n"
                '- "reason": brief explanation in Chinese (string)\n'
                "Respond ONLY with the JSON object."
            )

            from langchain_core.messages import HumanMessage

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content if hasattr(response, "content") else str(response)

            return parse_llm_verification(text)

        except Exception:
            logger.warning("LLM match verification failed", exc_info=True)
            return None


# Module-level LLM helper singleton
_llm_helper: PolicyLLMHelper | None = None


def _get_llm_helper() -> PolicyLLMHelper:
    """Get or create the module-level PolicyLLMHelper singleton."""
    global _llm_helper
    if _llm_helper is None:
        _llm_helper = PolicyLLMHelper()
    return _llm_helper


@router.post("/upload", response_model=ApiResponse[PolicyUploadResponse])
async def upload_policy(
    file: UploadFile = File(..., description="Policy PDF file to upload"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PolicyUploadResponse]:
    """Upload and process a policy PDF document.

    Validates the uploaded file (must be PDF, size limit enforced),
    extracts and chunks the content, generates embeddings, stores chunks
    in Qdrant policy_documents collection, extracts metadata via LLM,
    and persists metadata to the database.

    Returns document_id, title, chunk_count, page_count, status.
    """
    # Validate file type (T-11-07 mitigation)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ApiResponse(
            success=False,
            error="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # Read file content
    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc)
        return ApiResponse(
            success=False,
            error="Failed to read uploaded file. Please try again.",
        )

    # Validate file size (T-11-09 mitigation)
    max_size_bytes = rag_config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(pdf_bytes) > max_size_bytes:
        return ApiResponse(
            success=False,
            error=(
                f"File size exceeds maximum of {rag_config.MAX_FILE_SIZE_MB}MB. "
                f"Your file: {len(pdf_bytes) / (1024 * 1024):.1f}MB."
            ),
        )

    try:
        document_id = str(uuid4())
        safe_name = _sanitize_filename(file.filename)

        # Create upload directory if needed
        policy_upload_dir = os.path.join(rag_config.UPLOAD_DIR, "policies")
        os.makedirs(policy_upload_dir, exist_ok=True)

        file_path = os.path.join(policy_upload_dir, f"{document_id}_{safe_name}")

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        logger.info(
            "Saved policy PDF: id=%s file=%s size=%d bytes",
            document_id,
            safe_name,
            len(pdf_bytes),
        )

        # Extract PDF content
        content_blocks = extract_pdf_content(pdf_bytes)
        page_count = (
            max(block.get("page", 1) for block in content_blocks)
            if content_blocks
            else 1
        )

        # Build combined text for metadata extraction
        combined_text = "\n".join(block.get("content", "") for block in content_blocks)

        # Chunk into parents then children
        current_year = datetime.now(timezone.utc).year
        parents = chunk_into_parents(
            content_blocks,
            target_tokens=rag_config.PARENT_CHUNK_TOKENS,
        )

        # Override metadata fields for policy documents
        policy_parents: list[DocumentChunk] = []
        for parent in parents:
            new_metadata = replace(
                parent.metadata,
                document_id=document_id,
                ticker="policy",
                year=current_year,
                report_type="policy",
                company_name="",
                section="policy",
                filing_date=datetime.now(timezone.utc).isoformat(),
                chunk_type="parent",
            )
            policy_parents.append(
                DocumentChunk(
                    chunk_id=parent.chunk_id,
                    content=parent.content,
                    metadata=new_metadata,
                )
            )

        children = chunk_parents_into_children(
            policy_parents,
            target_tokens=rag_config.CHILD_CHUNK_TOKENS,
        )

        # Override child chunk_type metadata
        policy_children: list[DocumentChunk] = []
        for child in children:
            new_metadata = replace(
                child.metadata,
                chunk_type="child",
            )
            policy_children.append(
                DocumentChunk(
                    chunk_id=child.chunk_id,
                    content=child.content,
                    metadata=new_metadata,
                )
            )

        # Initialize QdrantVectorStore with policy_documents collection
        embedding_client = BGEEmbeddingClient()
        policy_store = QdrantVectorStore(
            url=rag_config.QDRANT_URL,
            collection="policy_documents",
            embedding_client=embedding_client,
        )
        policy_store.ensure_collection_exists()

        # Upsert child chunks to Qdrant
        if policy_children:
            await policy_store.upsert_chunks(policy_children)

        # Extract metadata via LLM
        llm_helper = _get_llm_helper()
        extracted_metadata = await llm_helper.extract_metadata(combined_text)

        # Build metadata with defaults if LLM fails
        if extracted_metadata is not None:
            title = extracted_metadata.get("title", safe_name)
            policy_type = extracted_metadata.get("policy_type", "unknown")
            issuing_body = extracted_metadata.get("issuing_body", "unknown")
            effective_date = extracted_metadata.get("effective_date")
            industry_tags = extracted_metadata.get("industry_tags", [])
        else:
            title = safe_name
            policy_type = "unknown"
            issuing_body = "unknown"
            effective_date = None
            industry_tags = []

        # Persist PolicyDocumentDB record
        policy_repo = PolicyDocumentRepository(db)
        create_data = PolicyDocumentCreate(
            document_id=document_id,
            title=title,
            policy_type=policy_type,
            issuing_body=issuing_body,
            effective_date=effective_date,
            industry_tags=industry_tags,
            file_path=file_path,
            page_count=page_count,
            chunk_count=len(policy_children),
        )
        await policy_repo.create(create_data)
        await db.commit()

        logger.info(
            "Policy upload completed: id=%s chunks=%d pages=%d",
            document_id,
            len(policy_children),
            page_count,
        )

        return ApiResponse(
            success=True,
            data=PolicyUploadResponse(
                document_id=document_id,
                title=title,
                chunk_count=len(policy_children),
                page_count=page_count,
                status="completed",
            ),
        )

    except Exception as exc:
        await db.rollback()
        logger.exception("Failed to process policy upload: %s", exc)
        return ApiResponse(
            success=False,
            error="Failed to process policy document upload. Please try again later.",
        )


@router.post("/resonance", response_model=ApiResponse[ResonanceResult])
async def analyze_resonance(
    request: ResonanceRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ResonanceResult]:
    """Analyze policy resonance for a given stock.

    Fetches the stock's business description, performs vector similarity
    search against the policy_documents Qdrant collection, verifies matches
    via LLM, calculates resonance score and DCF terminal growth adjustment.

    Returns resonance_score (0-100), tier, matched_policies, dcf_adjustment.
    """
    try:
        ticker = request.ticker.upper()

        # (1) Ensure stock exists
        market = Market.HK_SHARE if ticker.endswith(".HK") else Market.A_SHARE
        await ensure_stock_exists(ticker, market, data_service, db)

        # (2) Fetch business description
        desc_data = await data_service.get_business_description(ticker)
        main_business = desc_data.get("main_business", "")
        business_scope = desc_data.get("business_scope", "")

        # Concatenate: use main_business as primary; append business_scope
        # if main_business is too short for reliable matching
        if len(main_business) < 50 and business_scope:
            business_description = f"{main_business} {business_scope}"
        else:
            business_description = main_business

        if not business_description.strip():
            logger.warning(
                "Empty business description for %s, returning neutral resonance",
                ticker,
            )
            return _build_neutral_result(ticker, request.terminal_growth)

        # (3) Generate query embedding
        embedding_client = BGEEmbeddingClient()
        query_vector = await embedding_client.generate_query_embedding(
            business_description
        )

        # (4) Initialize QdrantVectorStore and search policy_documents
        policy_store = QdrantVectorStore(
            url=rag_config.QDRANT_URL,
            collection="policy_documents",
            embedding_client=embedding_client,
        )
        policy_store.ensure_collection_exists()

        results = await policy_store.search(
            query_vector=query_vector,
            limit=policy_resonance_config.MATCH_LIMIT,
            score_threshold=policy_resonance_config.VECTOR_SEARCH_THRESHOLD,
        )

        # (5) Handle empty collection: return neutral result
        if not results:
            logger.info("No policy documents found for %s resonance analysis", ticker)
            return _build_neutral_result(ticker, request.terminal_growth)

        # (6) Verify each match via LLM
        llm_helper = _get_llm_helper()
        verified_matches: list[dict[str, Any]] = []
        policy_match_objects: list[PolicyMatch] = []

        for result in results:
            payload = result.get("payload", {})
            chunk_content = payload.get("content", "")
            chunk_id = str(result.get("id", ""))
            doc_id = payload.get("document_id", "")
            score = result.get("score", 0.0)

            verification = await llm_helper.verify_match(
                business_description, chunk_content
            )

            if verification is not None:
                relevant = verification.get("relevant", False)
                confidence = verification.get("confidence", 0.0)
                reason = verification.get("reason", "")
            else:
                # LLM unavailable: mark as not verified
                relevant = False
                confidence = 0.0
                reason = "LLM verification unavailable"

            verified_matches.append(
                {
                    "score": score,
                    "relevant": relevant,
                    "confidence": confidence,
                    "reason": reason,
                }
            )

            policy_match_objects.append(
                PolicyMatch(
                    chunk_content=chunk_content,
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    score=score,
                    relevant=relevant,
                    confidence=confidence,
                    reason=reason,
                )
            )

        # (7) Calculate resonance score
        resonance_score = calculate_resonance_score(verified_matches)

        # (8) Calculate DCF adjustment using request.terminal_growth
        dcf_adjustment = calculate_dcf_adjustment(
            resonance_score=resonance_score,
            original_terminal_growth=request.terminal_growth,
        )

        # (9) Build and return ResonanceResult
        resonance_result = ResonanceResult(
            ticker=ticker,
            resonance_score=resonance_score,
            tier=dcf_adjustment.tier,
            matched_policies=policy_match_objects,
            dcf_adjustment=dcf_adjustment,
            policy_count=len(policy_match_objects),
            analyzed_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Policy resonance analysis completed: ticker=%s score=%.2f tier=%s",
            ticker,
            resonance_score,
            dcf_adjustment.tier.value,
        )

        return ApiResponse(success=True, data=resonance_result)

    except Exception:
        logger.exception(
            "Unexpected error in policy resonance analysis for %s",
            request.ticker,
        )
        return ApiResponse(
            success=False,
            error="An internal error occurred during policy resonance analysis. "
            "Please try again later.",
        )


def _build_neutral_result(
    ticker: str, terminal_growth: float
) -> ApiResponse[ResonanceResult]:
    """Build a neutral ResonanceResult for empty-collection or empty-description cases.

    Args:
        ticker: Stock ticker code.
        terminal_growth: Base terminal growth rate from request.

    Returns:
        ApiResponse with neutral ResonanceResult (score=0, tier=NEUTRAL).
    """
    neutral_adjustment = DCFAdjustment(
        tier=ResonanceTier.NEUTRAL,
        adjustment_pct=0.0,
        adjusted_terminal_growth=terminal_growth,
        original_terminal_growth=terminal_growth,
    )
    result = ResonanceResult(
        ticker=ticker,
        resonance_score=0.0,
        tier=ResonanceTier.NEUTRAL,
        matched_policies=[],
        dcf_adjustment=neutral_adjustment,
        policy_count=0,
        analyzed_at=datetime.now(timezone.utc),
    )
    return ApiResponse(success=True, data=result)


__all__ = [
    "router",
]
