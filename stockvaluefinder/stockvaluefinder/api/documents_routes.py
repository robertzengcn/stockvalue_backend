"""Document upload, search, and management API endpoints.

Provides endpoints for uploading PDF annual reports, checking processing
status, performing semantic search across indexed documents, and deleting
documents. Uploads are processed asynchronously via FastAPI BackgroundTasks.
"""

import logging
import re
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.document import (
    DocumentSearchRequest,
    DocumentUploadResponse,
)
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.retriever import SearchResult, SemanticRetriever
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.repositories.document_repo import DocumentRepository
from stockvaluefinder.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# Ticker format validation pattern
_TICKER_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|HK)$")


class DocumentStatusResponse(BaseModel):
    """Response model for document status queries.

    Attributes:
        document_id: UUID of the document.
        status: Current processing status (pending, processing, completed, failed).
        page_count: Number of pages in the PDF.
        chunk_count: Number of chunks generated.
    """

    document_id: str = Field(..., description="Document UUID")
    status: str = Field(..., description="Processing status")
    page_count: int = Field(default=0, ge=0, description="Number of pages")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks")

    model_config = {"frozen": True}


class _UploadForm(BaseModel):
    """Validated form fields for document upload.

    Attributes:
        ticker: Stock ticker this document belongs to.
        year: Fiscal year of the report.
        report_type: Type of report (annual, quarterly).
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH')",
    )
    year: int = Field(..., ge=2000, le=2100, description="Fiscal year")
    report_type: str = Field(default="annual", description="Report type")

    model_config = {"frozen": True}


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing path traversal characters.

    Strips directory components and removes characters that could
    be used for path traversal attacks.

    Args:
        filename: Original filename to sanitize.

    Returns:
        Sanitized filename with only safe characters retained.
    """
    # Remove any directory components
    safe_name = filename.replace("\\", "/").split("/")[-1]
    # Remove non-alphanumeric characters except dots, dashes, underscores
    safe_name = re.sub(r"[^\w.\-]", "_", safe_name)
    return safe_name


def _build_document_service(db: AsyncSession) -> DocumentService:
    """Construct a DocumentService with default RAG components.

    Args:
        db: Async database session.

    Returns:
        DocumentService instance with QdrantVectorStore and BGEEmbeddingClient.
    """
    embedding_client = BGEEmbeddingClient()
    vector_store = QdrantVectorStore(
        url=rag_config.QDRANT_URL,
        collection=rag_config.QDRANT_COLLECTION,
        api_key=rag_config.QDRANT_API_KEY,
        embedding_client=embedding_client,
    )
    document_repo = DocumentRepository(db)
    return DocumentService(
        db_session=db,
        embedding_client=embedding_client,
        vector_store=vector_store,
        document_repo=document_repo,
    )


async def _process_upload_background(
    document_id: str,
    ticker: str,
    file_name: str,
    file_path: str,
    pdf_bytes: bytes,
    db: AsyncSession,
) -> None:
    """Background task that processes an uploaded PDF through the RAG pipeline.

    Creates its own DocumentService instance and handles errors gracefully,
    logging any failures during processing.

    Args:
        document_id: UUID of the created document record.
        ticker: Stock ticker this document belongs to.
        file_name: Original uploaded file name.
        file_path: Storage path for the PDF file.
        pdf_bytes: Raw PDF file bytes.
        db: Async database session.
    """
    try:
        service = _build_document_service(db)
        result = await service.process_upload(
            document_id=document_id,
            ticker=ticker,
            file_name=file_name,
            file_path=file_path,
            pdf_bytes=pdf_bytes,
        )
        await db.commit()
        logger.info(
            "Background processing completed for document %s: %d chunks",
            document_id,
            result.chunk_count,
        )
    except Exception:
        await db.rollback()
        logger.exception(
            "Background processing failed for document %s",
            document_id,
        )


@router.post("/upload", response_model=ApiResponse[DocumentUploadResponse])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload"),
    ticker: str = Form(..., description="Stock ticker (e.g., '600519.SH')"),
    year: int = Form(..., description="Fiscal year"),
    report_type: str = Form("annual", description="Report type"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentUploadResponse]:
    """Upload and process a PDF annual report.

    Validates the uploaded file (must be PDF, valid ticker, size limit),
    creates a document record in the database, and queues background
    processing (parse, chunk, embed, store in Qdrant).

    Returns immediately with document_id and status='processing'.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ApiResponse(
            success=False,
            error="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # Validate ticker format
    if not _TICKER_PATTERN.match(ticker):
        return ApiResponse(
            success=False,
            error=f"Invalid ticker format: '{ticker}'. Expected format: 600519.SH",
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

    # Validate file size
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
        # Sanitize filename and generate storage path
        safe_name = _sanitize_filename(file.filename)
        document_id = str(uuid4())
        file_path = f"{rag_config.UPLOAD_DIR}/{document_id}_{safe_name}"

        # Create document record in database
        document_repo = DocumentRepository(db)
        await document_repo.create_document(
            ticker=ticker.upper(),
            file_name=safe_name,
            file_path=file_path,
            page_count=0,  # Updated after processing
            metadata={"year": year, "report_type": report_type},
        )
        await db.commit()

        # Get the created document's actual ID
        doc_record = await document_repo.get_by_ticker(ticker.upper(), limit=1)
        actual_document_id = doc_record[0].document_id if doc_record else document_id

        # Queue background processing
        background_tasks.add_task(
            _process_upload_background,
            actual_document_id,
            ticker.upper(),
            safe_name,
            file_path,
            pdf_bytes,
            db,
        )

        logger.info(
            "Queued document upload: id=%s ticker=%s file=%s",
            actual_document_id,
            ticker,
            safe_name,
        )

        return ApiResponse(
            success=True,
            data=DocumentUploadResponse(
                document_id=actual_document_id,
                status="processing",
                chunk_count=0,
                page_count=0,
            ),
        )

    except Exception as exc:
        await db.rollback()
        logger.exception("Failed to create document record: %s", exc)
        return ApiResponse(
            success=False,
            error="Failed to process document upload. Please try again later.",
        )


@router.get(
    "/{document_id}/status",
    response_model=ApiResponse[DocumentStatusResponse],
)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentStatusResponse]:
    """Get the current processing status of a document.

    Returns the document's processing status, page count, and chunk count.
    """
    try:
        service = _build_document_service(db)
        status_info = await service.get_document_status(document_id)

        if status_info is None:
            return ApiResponse(
                success=False,
                error=f"Document not found: {document_id}",
            )

        return ApiResponse(
            success=True,
            data=DocumentStatusResponse(
                document_id=document_id,
                status=status_info["status"],
                page_count=status_info["page_count"],
                chunk_count=status_info["chunk_count"],
            ),
        )

    except Exception as exc:
        logger.exception(
            "Failed to get status for document %s: %s",
            document_id,
            exc,
        )
        return ApiResponse(
            success=False,
            error="Failed to retrieve document status. Please try again later.",
        )


@router.post("/search", response_model=ApiResponse[list[dict[str, object]]])
async def search_documents(
    request: DocumentSearchRequest,
) -> ApiResponse[list[dict[str, object]]]:
    """Semantic search across indexed documents.

    Performs semantic search with optional ticker/year filtering.
    When multi-query expansion is enabled, generates query variations
    for improved recall.
    """
    try:
        # Build retriever with default config
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

        if request.use_multi_query:
            results = await retriever.search_with_multi_query_expansion(
                query=request.query,
                ticker=request.ticker,
                year=request.year,
                limit=request.limit,
                score_threshold=request.score_threshold,
            )
        else:
            results = await retriever.search(
                query=request.query,
                ticker=request.ticker,
                year=request.year,
                limit=request.limit,
                score_threshold=request.score_threshold,
            )

        # Convert SearchResult dataclasses to dicts for JSON serialization
        result_dicts = [_search_result_to_dict(r) for r in results]

        return ApiResponse(
            success=True,
            data=result_dicts,
            meta={"total": len(result_dicts)},
        )

    except Exception as exc:
        logger.exception("Document search failed: %s", exc)
        return ApiResponse(
            success=False,
            error="Search failed. Please try again later.",
        )


@router.delete("/{document_id}", response_model=ApiResponse[dict[str, str]])
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, str]]:
    """Delete a document from both Qdrant and the database.

    Removes all associated chunks from the vector store and deletes
    the document metadata record.
    """
    try:
        service = _build_document_service(db)
        deleted = await service.delete_document(document_id)

        if not deleted:
            return ApiResponse(
                success=False,
                error=f"Document not found: {document_id}",
            )

        await db.commit()

        logger.info("Deleted document: %s", document_id)
        return ApiResponse(
            success=True,
            data={"document_id": document_id, "status": "deleted"},
        )

    except Exception as exc:
        await db.rollback()
        logger.exception("Failed to delete document %s: %s", document_id, exc)
        return ApiResponse(
            success=False,
            error="Failed to delete document. Please try again later.",
        )


def _search_result_to_dict(result: SearchResult) -> dict[str, object]:
    """Convert a SearchResult dataclass to a JSON-serializable dict.

    Args:
        result: SearchResult to convert.

    Returns:
        Dictionary with all SearchResult fields.
    """
    return {
        "chunk_id": result.chunk_id,
        "content": result.content,
        "parent_content": result.parent_content,
        "page_number": result.page_number,
        "section": result.section,
        "score": result.score,
        "ticker": result.ticker,
        "year": result.year,
    }


__all__ = [
    "router",
    "DocumentStatusResponse",
]
