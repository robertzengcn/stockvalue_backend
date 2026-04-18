"""Document service layer for RAG pipeline orchestration.

Orchestrates the full document upload pipeline:
parse PDF -> chunk into parents -> chunk parents into children ->
generate embeddings -> upsert chunks into Qdrant.

Each step updates the processing_status in the database, enabling
status tracking and failure recovery.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.config import rag_config
from stockvaluefinder.models.document import DocumentUploadResponse
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.repositories.document_repo import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentService:
    """Service that orchestrates the document upload and processing pipeline.

    Coordinates PDF parsing, parent-child chunking, embedding generation,
    and vector store upserts. Tracks processing status through the
    DocumentRepository.

    Attributes:
        db_session: Async database session for transaction management.
        pdf_processor: Module with PDF parsing and chunking functions.
        embedding_client: Client for generating bge-m3 embeddings.
        vector_store: Qdrant vector store for chunk storage.
        document_repo: Repository for document metadata persistence.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        pdf_processor: Any = None,
        embedding_client: BGEEmbeddingClient | None = None,
        vector_store: QdrantVectorStore | None = None,
        document_repo: DocumentRepository | None = None,
    ) -> None:
        """Initialize DocumentService with injected dependencies.

        Args:
            db_session: Async database session.
            pdf_processor: Module providing extract_pdf_content,
                chunk_into_parents, chunk_parents_into_children.
                Defaults to the rag.pdf_processor module.
            embedding_client: Client for bge-m3 embedding generation.
                Defaults to a new BGEEmbeddingClient.
            vector_store: Qdrant vector store instance.
                Defaults to a new QdrantVectorStore.
            document_repo: Repository for document metadata.
                Defaults to a new DocumentRepository with the given session.
        """
        self.db_session = db_session
        self.pdf_processor = (
            pdf_processor if pdf_processor is not None else _default_pdf_processor()
        )
        self.embedding_client = embedding_client or BGEEmbeddingClient()
        self.vector_store = vector_store or QdrantVectorStore(
            embedding_client=self.embedding_client,
        )
        self.document_repo = document_repo or DocumentRepository(db_session)

    async def process_upload(
        self,
        document_id: str,
        ticker: str,
        file_name: str,
        file_path: str,
        pdf_bytes: bytes,
    ) -> DocumentUploadResponse:
        """Process an uploaded PDF through the full RAG pipeline.

        Orchestrates: parse -> chunk -> embed -> store, updating
        processing_status at each step (pending -> processing -> completed).
        On failure, sets status to 'failed' and re-raises the exception.

        Args:
            document_id: UUID of the existing document record.
            ticker: Stock ticker this document belongs to.
            file_name: Original uploaded file name.
            file_path: Storage path for the PDF file.
            pdf_bytes: Raw PDF file bytes.

        Returns:
            DocumentUploadResponse with document_id, status, chunk_count,
            and page_count.

        Raises:
            ValueError: If file size exceeds the configured maximum.
            DataValidationError: If the PDF is invalid or cannot be parsed.
            ExternalAPIError: If embedding generation fails.
        """
        max_size_bytes = rag_config.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(pdf_bytes) > max_size_bytes:
            raise ValueError(
                f"File size exceeds maximum of {rag_config.MAX_FILE_SIZE_MB}MB"
            )

        try:
            # Step 1: Mark as processing
            await self.document_repo.update_status(document_id, "processing")

            # Step 2: Extract PDF content
            content_blocks = self.pdf_processor.extract_pdf_content(pdf_bytes)
            page_count = max(
                (block.get("page", 1) for block in content_blocks),
                default=0,
            )

            # Step 3: Chunk into parents
            parent_chunks = self.pdf_processor.chunk_into_parents(content_blocks)

            # Step 4: Chunk parents into children
            child_chunks = self.pdf_processor.chunk_parents_into_children(parent_chunks)

            # Step 5: Update chunk metadata with document context
            enriched_chunks = _enrich_chunk_metadata(
                child_chunks,
                document_id=document_id,
                ticker=ticker,
            )

            # Step 6: Upsert into vector store (generates embeddings internally)
            await self.vector_store.upsert_chunks(enriched_chunks)

            # Step 7: Update metadata with chunk count and mark completed
            current_doc = await self.document_repo.get_by_document_id(document_id)
            existing_metadata = current_doc.metadata_ if current_doc else {}
            updated_metadata = {
                **existing_metadata,
                "chunk_count": len(enriched_chunks),
                "page_count": page_count,
            }
            await self.document_repo.update_metadata(document_id, updated_metadata)
            await self.document_repo.update_status(document_id, "completed")

            logger.info(
                "Processed document %s: %d chunks from %d pages",
                document_id,
                len(enriched_chunks),
                page_count,
            )

            return DocumentUploadResponse(
                document_id=document_id,
                status="completed",
                chunk_count=len(enriched_chunks),
                page_count=page_count,
            )

        except Exception:
            # Attempt to mark as failed, but don't mask the original error
            try:
                await self.document_repo.update_status(document_id, "failed")
            except Exception:
                logger.exception(
                    "Failed to update status to 'failed' for document %s",
                    document_id,
                )
            raise

    async def get_document_status(self, document_id: str) -> dict[str, Any] | None:
        """Get the current processing status of a document.

        Args:
            document_id: UUID of the document to check.

        Returns:
            Dictionary with status, page_count, and chunk_count,
            or None if the document does not exist.
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if doc is None:
            return None

        metadata = doc.metadata_ or {}
        return {
            "status": doc.processing_status,
            "page_count": doc.page_count,
            "chunk_count": metadata.get("chunk_count", 0),
        }

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from both Qdrant and the database.

        Removes all chunks from the vector store first, then deletes
        the document metadata record. If the database delete fails,
        the Qdrant data is still removed (best-effort cleanup).

        Args:
            document_id: UUID of the document to delete.

        Returns:
            True if the document was found and deleted, False otherwise.
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if doc is None:
            return False

        # Always attempt Qdrant cleanup
        self.vector_store.delete_by_document_id(document_id)

        # Delete from database
        deleted = await self.document_repo.delete(document_id)

        if deleted:
            logger.info("Deleted document %s from Qdrant and database", document_id)
        else:
            logger.warning(
                "Deleted document %s from Qdrant but DB delete returned False",
                document_id,
            )

        return deleted


def _default_pdf_processor() -> Any:
    """Return the default pdf_processor module.

    Returns:
        The rag.pdf_processor module with extract_pdf_content,
        chunk_into_parents, and chunk_parents_into_children functions.
    """
    import stockvaluefinder.rag.pdf_processor as module

    return module


def _enrich_chunk_metadata(
    chunks: list[Any],
    document_id: str,
    ticker: str,
) -> list[Any]:
    """Update chunk metadata with document_id and ticker.

    Creates new DocumentChunk instances with updated metadata,
    preserving immutability of the original chunks.

    Args:
        chunks: List of DocumentChunk objects to enrich.
        document_id: Document UUID to set on each chunk.
        ticker: Stock ticker to set on each chunk.

    Returns:
        New list of DocumentChunk objects with enriched metadata.
    """
    from stockvaluefinder.models.document import ChunkMetadata, DocumentChunk

    enriched: list[DocumentChunk] = []
    for chunk in chunks:
        original_meta = chunk.metadata
        new_metadata = ChunkMetadata(
            document_id=document_id,
            parent_id=original_meta.parent_id,
            page_number=original_meta.page_number,
            section=original_meta.section,
            ticker=ticker,
            year=original_meta.year,
            report_type=original_meta.report_type,
            company_name=original_meta.company_name,
            filing_date=original_meta.filing_date,
            chunk_type=original_meta.chunk_type,
            token_count=original_meta.token_count,
        )
        enriched.append(
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                metadata=new_metadata,
            )
        )
    return enriched


__all__ = [
    "DocumentService",
]
