"""Pydantic and dataclass models for Document RAG pipeline."""

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to every chunk stored in Qdrant.

    Attributes:
        document_id: UUID of the source document
        parent_id: UUID of the parent chunk (None for parent chunks)
        page_number: Original page number in the PDF (1-based)
        section: Document section heading (e.g., "financial_statements")
        ticker: Stock ticker this document belongs to
        year: Fiscal year of the report
        report_type: Type of report (e.g., "annual", "quarterly")
        company_name: Name of the company
        filing_date: Date the report was filed (ISO format)
        chunk_type: Type of chunk ("parent", "child", or "table")
        token_count: Number of tokens in the chunk content
    """

    document_id: str
    parent_id: str | None
    page_number: int
    section: str
    ticker: str
    year: int
    report_type: str
    company_name: str
    filing_date: str
    chunk_type: str
    token_count: int


@dataclass(frozen=True)
class DocumentChunk:
    """A single chunk extracted from a PDF document.

    Attributes:
        chunk_id: Unique identifier for this chunk
        content: The text content of the chunk
        metadata: Metadata associated with this chunk
    """

    chunk_id: str
    content: str
    metadata: ChunkMetadata


class DocumentUploadResponse(BaseModel):
    """Response model returned after a successful document upload.

    Attributes:
        document_id: UUID of the created document record
        status: Current processing status
        chunk_count: Number of chunks generated (0 if still processing)
        page_count: Number of pages in the uploaded PDF
    """

    document_id: str = Field(..., description="UUID of the created document record")
    status: str = Field(
        ..., description="Current processing status (pending, processing, completed)"
    )
    chunk_count: int = Field(
        ..., ge=0, description="Number of chunks generated (0 if still processing)"
    )
    page_count: int = Field(
        ..., ge=1, description="Number of pages in the uploaded PDF"
    )

    model_config = {"frozen": True}


class DocumentSearchRequest(BaseModel):
    """Request model for semantic document search.

    Attributes:
        query: The search query text
        ticker: Optional ticker filter to narrow results
        year: Optional year filter to narrow results
        limit: Maximum number of results to return
        score_threshold: Minimum relevance score (0.0 to 1.0)
        use_multi_query: Whether to use multi-query expansion for better recall
    """

    query: str = Field(..., min_length=1, description="Search query text")
    ticker: str | None = Field(
        None,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Optional ticker filter",
    )
    year: int | None = Field(None, ge=2000, le=2100, description="Optional year filter")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    score_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum relevance score"
    )
    use_multi_query: bool = Field(
        default=True, description="Enable multi-query expansion for better recall"
    )

    model_config = {"frozen": True}

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "query": "贵州茅台2023年营业收入",
                    "ticker": "600519.SH",
                    "year": 2023,
                    "limit": 10,
                    "score_threshold": 0.7,
                    "use_multi_query": True,
                },
                {
                    "query": "risk factors related to debt",
                    "limit": 5,
                    "score_threshold": 0.8,
                },
            ]
        }
