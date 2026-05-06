"""Policy resonance domain models (Pydantic).

This module defines all Pydantic models for the Policy Resonance Engine,
which measures how well a stock aligns with government policy direction
through document-based semantic matching.

Key models:
    - PolicyMatch: A single matched policy chunk with LLM verification
    - PolicyMetadata: Metadata extracted from policy documents
    - DCFAdjustment: DCF terminal growth adjustment result
    - ResonanceResult: Full resonance analysis result
    - ResonanceRequest: Request for resonance analysis
    - PolicyUploadResponse: Response after policy document upload
    - PolicyMetadataExtraction: LLM-extracted metadata from policy content
"""

from datetime import datetime

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import ResonanceTier


class PolicyMatch(BaseModel):
    """A single matched policy chunk with LLM verification results (D-05).

    Represents a policy document chunk that was matched to a stock's business
    description via vector similarity and verified by LLM classification.

    Attributes:
        chunk_content: The text content of the matched policy chunk.
        chunk_id: Unique identifier for this chunk.
        document_id: UUID of the source policy document.
        score: Cosine similarity score (0.0 to 1.0).
        relevant: Whether LLM confirmed the match as relevant.
        confidence: LLM confidence score (0.0 to 1.0).
        reason: LLM explanation for the relevance verdict.
    """

    chunk_content: str = Field(
        ..., description="Text content of the matched policy chunk"
    )
    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    document_id: str = Field(..., description="UUID of the source policy document")
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score (0-1)"
    )
    relevant: bool = Field(
        ..., description="Whether LLM confirmed the match as relevant"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM confidence score (0-1)"
    )
    reason: str = Field(..., description="LLM explanation for the relevance verdict")

    model_config = {"frozen": True}


class PolicyMetadata(BaseModel):
    """Metadata extracted from a policy document (D-10).

    Enriched metadata per policy document: title, policy type, issuing body,
    effective date, and industry tags. LLM auto-extracts these during upload
    processing.

    Attributes:
        title: Policy document title.
        policy_type: Type of policy (industry/fiscal/monetary/trade).
        issuing_body: Government body that issued the policy.
        effective_date: Date the policy takes effect (ISO format), or None.
        industry_tags: List of industry tags relevant to this policy.
    """

    title: str = Field(..., description="Policy document title")
    policy_type: str = Field(
        ..., description="Type of policy (industry/fiscal/monetary/trade)"
    )
    issuing_body: str = Field(..., description="Government body that issued the policy")
    effective_date: str | None = Field(
        None, description="Date the policy takes effect (ISO format)"
    )
    industry_tags: list[str] = Field(
        default_factory=list, description="Industry tags relevant to this policy"
    )

    model_config = {"frozen": True}


class DCFAdjustment(BaseModel):
    """DCF terminal growth adjustment result (D-07, D-08).

    Represents the adjustment to DCF terminal growth rate based on
    policy resonance tier classification.

    Attributes:
        tier: Resonance tier classification.
        adjustment_pct: Adjustment percentage (e.g., 0.015 = +1.5%).
        adjusted_terminal_growth: Terminal growth after adjustment and clamping.
        original_terminal_growth: Original terminal growth rate before adjustment.
    """

    tier: ResonanceTier = Field(..., description="Resonance tier classification")
    adjustment_pct: float = Field(
        ..., description="Adjustment percentage (e.g. 0.015 = +1.5%)"
    )
    adjusted_terminal_growth: float = Field(
        ..., description="Terminal growth after adjustment and clamping"
    )
    original_terminal_growth: float = Field(
        ..., description="Original terminal growth rate before adjustment"
    )

    model_config = {"frozen": True}


class ResonanceResult(BaseModel):
    """Full resonance analysis result (D-09).

    Combined API response containing resonance score, tier label, matched
    policy excerpts, and DCF adjustment details.

    Attributes:
        ticker: Stock code (e.g., '600519.SH').
        resonance_score: Policy resonance score (0-100).
        tier: Resonance tier classification.
        matched_policies: List of matched policy chunks with verification.
        dcf_adjustment: DCF terminal growth adjustment result.
        policy_count: Number of matched policies.
        analyzed_at: Timestamp of analysis.
    """

    ticker: str = Field(..., description="Stock code")
    resonance_score: float = Field(
        ..., ge=0.0, le=100.0, description="Policy resonance score (0-100)"
    )
    tier: ResonanceTier = Field(..., description="Resonance tier classification")
    matched_policies: list[PolicyMatch] = Field(
        ..., description="List of matched policy chunks with verification"
    )
    dcf_adjustment: DCFAdjustment = Field(
        ..., description="DCF terminal growth adjustment result"
    )
    policy_count: int = Field(..., ge=0, description="Number of matched policies")
    analyzed_at: datetime = Field(..., description="Timestamp of analysis")

    model_config = {"frozen": True}


class PolicyUploadResponse(BaseModel):
    """Response after policy document upload.

    Attributes:
        document_id: UUID of the created document record.
        title: Title of the uploaded policy document.
        chunk_count: Number of chunks generated.
        page_count: Number of pages in the uploaded PDF.
        status: Current processing status.
    """

    document_id: str = Field(..., description="UUID of the created document record")
    title: str = Field(..., description="Title of the uploaded policy document")
    chunk_count: int = Field(..., ge=0, description="Number of chunks generated")
    page_count: int = Field(
        ..., ge=1, description="Number of pages in the uploaded PDF"
    )
    status: str = Field(
        ..., description="Current processing status (pending, processing, completed)"
    )

    model_config = {"frozen": True}


class ResonanceRequest(BaseModel):
    """Request model for resonance analysis.

    Attributes:
        ticker: Stock code matching pattern NNNNNN.{SH|SZ|HK}.
        terminal_growth: Base terminal growth rate for DCF adjustment calculation.
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., 600519.SH)",
    )
    terminal_growth: float = Field(
        default=0.025,
        description="Base terminal growth rate for DCF adjustment calculation",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH", "terminal_growth": 0.025},
                {"ticker": "000002.SZ"},
            ]
        }


class PolicyMetadataExtraction(BaseModel):
    """LLM-extracted metadata from policy document content (D-10).

    Used for parsing structured metadata from LLM output during
    policy document upload processing.

    Attributes:
        title: Policy document title.
        policy_type: Type of policy (industry/fiscal/monetary/trade).
        issuing_body: Government body that issued the policy.
        effective_date: Date the policy takes effect (ISO format), or None.
        industry_tags: List of industry tags relevant to this policy.
    """

    title: str = Field(..., description="Policy document title")
    policy_type: str = Field(
        ..., description="Type of policy (industry/fiscal/monetary/trade)"
    )
    issuing_body: str = Field(..., description="Government body that issued the policy")
    effective_date: str | None = Field(
        None, description="Date the policy takes effect (ISO format)"
    )
    industry_tags: list[str] = Field(
        default_factory=list, description="Industry tags relevant to this policy"
    )


class PolicyDocumentCreate(BaseModel):
    """Model for creating a policy document in the database.

    Used for persistence via the repository layer. Contains metadata
    extracted from the uploaded policy PDF.

    Attributes:
        document_id: UUID for this document.
        title: Policy document title.
        policy_type: Type of policy (industry/fiscal/monetary/trade).
        issuing_body: Government body that issued the policy.
        effective_date: Date the policy takes effect (ISO format), or None.
        industry_tags: List of industry tags relevant to this policy.
        file_path: Server-side file path to the stored PDF.
        page_count: Number of pages in the PDF.
        chunk_count: Number of chunks generated from the PDF.
    """

    document_id: str = Field(..., description="UUID for this document")
    title: str = Field(..., description="Policy document title")
    policy_type: str = Field(
        ..., description="Type of policy (industry/fiscal/monetary/trade)"
    )
    issuing_body: str = Field(..., description="Government body that issued the policy")
    effective_date: str | None = Field(
        None, description="Date the policy takes effect (ISO format)"
    )
    industry_tags: list[str] = Field(
        default_factory=list, description="Industry tags relevant to this policy"
    )
    file_path: str = Field(..., description="Server-side file path to the stored PDF")
    page_count: int = Field(..., ge=1, description="Number of pages in the PDF")
    chunk_count: int = Field(
        default=0, ge=0, description="Number of chunks generated from the PDF"
    )


class PolicyDocumentUpdate(BaseModel):
    """Model for updating a policy document.

    Used by the repository layer for partial updates. All fields are
    optional -- only provided fields will be updated.

    Attributes:
        title: Updated title.
        chunk_count: Updated chunk count after reprocessing.
        industry_tags: Updated industry tags.
    """

    title: str | None = None
    chunk_count: int | None = None
    industry_tags: list[str] | None = None
