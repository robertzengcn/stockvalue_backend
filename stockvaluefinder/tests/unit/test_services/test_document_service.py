"""Unit tests for DocumentService orchestration layer.

Tests the full upload pipeline: parse -> chunk -> embed -> store,
status tracking, and document deletion. External dependencies
(pdf_processor, embedding_client, vector_store, document_repo)
are mocked to isolate service logic.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.models.document import (
    ChunkMetadata,
    DocumentChunk,
    DocumentUploadResponse,
)
from stockvaluefinder.services.document_service import DocumentService


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock async database session."""
    return AsyncMock()


@pytest.fixture
def mock_pdf_processor() -> MagicMock:
    """Create a mock pdf_processor module."""
    processor = MagicMock()
    processor.extract_pdf_content = MagicMock(
        return_value=[
            {
                "type": "text",
                "content": "Page 1 text",
                "page": 1,
                "bbox": (0, 0, 100, 100),
            },
            {
                "type": "text",
                "content": "Page 2 text",
                "page": 2,
                "bbox": (0, 0, 100, 100),
            },
        ]
    )
    return processor


@pytest.fixture
def mock_embedding_client() -> AsyncMock:
    """Create a mock BGEEmbeddingClient."""
    return AsyncMock()


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create a mock QdrantVectorStore."""
    store = AsyncMock()
    store.delete_by_document_id = MagicMock()
    return store


@pytest.fixture
def mock_document_repo() -> AsyncMock:
    """Create a mock DocumentRepository."""
    return AsyncMock()


@pytest.fixture
def document_service(
    mock_db_session: AsyncMock,
    mock_pdf_processor: MagicMock,
    mock_embedding_client: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_document_repo: AsyncMock,
) -> DocumentService:
    """Create a DocumentService with mocked dependencies."""
    return DocumentService(
        db_session=mock_db_session,
        pdf_processor=mock_pdf_processor,
        embedding_client=mock_embedding_client,
        vector_store=mock_vector_store,
        document_repo=mock_document_repo,
    )


def _make_parent_chunk(
    chunk_id: str = "parent-1", content: str = "Parent content"
) -> DocumentChunk:
    """Create a test parent chunk."""
    return DocumentChunk(
        chunk_id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            document_id="doc-123",
            parent_id=None,
            page_number=1,
            section="",
            ticker="600519.SH",
            year=2023,
            report_type="annual",
            company_name="Test Company",
            filing_date="2024-03-28",
            chunk_type="parent",
            token_count=10,
        ),
    )


def _make_child_chunk(
    chunk_id: str = "child-1",
    parent_id: str = "parent-1",
    content: str = "Child content",
) -> DocumentChunk:
    """Create a test child chunk."""
    return DocumentChunk(
        chunk_id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            document_id="doc-123",
            parent_id=parent_id,
            page_number=1,
            section="",
            ticker="600519.SH",
            year=2023,
            report_type="annual",
            company_name="Test Company",
            filing_date="2024-03-28",
            chunk_type="child",
            token_count=5,
        ),
    )


def _setup_repo_mocks(mock_document_repo: AsyncMock) -> None:
    """Configure standard document_repo mock responses for pipeline tests."""
    mock_doc = MagicMock()
    mock_doc.metadata_ = {}
    mock_document_repo.update_status = AsyncMock(return_value=MagicMock())
    mock_document_repo.get_by_document_id = AsyncMock(return_value=mock_doc)
    mock_document_repo.update_metadata = AsyncMock(return_value=mock_doc)


class TestDocumentServiceInit:
    """Tests for DocumentService initialization."""

    def test_init_stores_dependencies(
        self,
        mock_db_session: AsyncMock,
        mock_pdf_processor: MagicMock,
        mock_embedding_client: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """DocumentService stores all injected dependencies."""
        service = DocumentService(
            db_session=mock_db_session,
            pdf_processor=mock_pdf_processor,
            embedding_client=mock_embedding_client,
            vector_store=mock_vector_store,
            document_repo=mock_document_repo,
        )
        assert service.db_session is mock_db_session
        assert service.pdf_processor is mock_pdf_processor
        assert service.embedding_client is mock_embedding_client
        assert service.vector_store is mock_vector_store
        assert service.document_repo is mock_document_repo


class TestProcessUpload:
    """Tests for process_upload orchestration."""

    @pytest.mark.asyncio
    async def test_process_upload_full_pipeline(
        self,
        document_service: DocumentService,
        mock_pdf_processor: MagicMock,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload orchestrates parse -> chunk -> embed -> store."""
        # Arrange
        parent_chunks = [_make_parent_chunk("p1", "Parent text")]
        child_chunks = [
            _make_child_chunk("c1", "p1", "Child text 1"),
            _make_child_chunk("c2", "p1", "Child text 2"),
        ]

        _setup_repo_mocks(mock_document_repo)
        mock_pdf_processor.extract_pdf_content.return_value = [
            {"type": "text", "content": "Some text", "page": 1, "bbox": (0, 0, 1, 1)},
        ]
        mock_pdf_processor.chunk_into_parents.return_value = parent_chunks
        mock_pdf_processor.chunk_parents_into_children.return_value = child_chunks
        mock_vector_store.upsert_chunks = AsyncMock()

        pdf_bytes = b"%PDF-1.4 fake pdf content"

        # Act
        result = await document_service.process_upload(
            document_id="doc-123",
            ticker="600519.SH",
            file_name="test_report.pdf",
            file_path="/uploads/test_report.pdf",
            pdf_bytes=pdf_bytes,
        )

        # Assert
        assert isinstance(result, DocumentUploadResponse)
        assert result.document_id == "doc-123"
        assert result.status == "completed"
        assert result.chunk_count == 2
        assert result.page_count >= 1

        # Verify pipeline calls
        mock_pdf_processor.extract_pdf_content.assert_called_once_with(pdf_bytes)
        mock_pdf_processor.chunk_into_parents.assert_called_once()
        mock_pdf_processor.chunk_parents_into_children.assert_called_once_with(
            parent_chunks
        )
        # upsert_chunks is called with enriched chunks (2 items)
        mock_vector_store.upsert_chunks.assert_called_once()
        upserted_chunks = mock_vector_store.upsert_chunks.call_args[0][0]
        assert len(upserted_chunks) == 2
        # Verify enrichment: document_id and ticker updated
        for chunk in upserted_chunks:
            assert chunk.metadata.document_id == "doc-123"
            assert chunk.metadata.ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_process_upload_status_tracking(
        self,
        document_service: DocumentService,
        mock_pdf_processor: MagicMock,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload updates processing_status: pending -> processing -> completed."""
        # Arrange
        _setup_repo_mocks(mock_document_repo)
        mock_pdf_processor.extract_pdf_content.return_value = [
            {"type": "text", "content": "text", "page": 1, "bbox": (0, 0, 1, 1)},
        ]
        mock_pdf_processor.chunk_into_parents.return_value = [_make_parent_chunk()]
        mock_pdf_processor.chunk_parents_into_children.return_value = [
            _make_child_chunk()
        ]
        mock_vector_store.upsert_chunks = AsyncMock()

        # Act
        await document_service.process_upload(
            document_id="doc-456",
            ticker="600519.SH",
            file_name="report.pdf",
            file_path="/uploads/report.pdf",
            pdf_bytes=b"%PDF-1.4 test",
        )

        # Assert: status was updated at each step
        status_calls = mock_document_repo.update_status.call_args_list
        statuses = [call[0][1] for call in status_calls]

        assert "processing" in statuses
        assert "completed" in statuses
        # processing should come before completed
        assert statuses.index("processing") < statuses.index("completed")

    @pytest.mark.asyncio
    async def test_process_upload_failed_on_error(
        self,
        document_service: DocumentService,
        mock_pdf_processor: MagicMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload sets status to failed on processing error."""
        # Arrange
        mock_document_repo.update_status = AsyncMock(return_value=MagicMock())
        mock_pdf_processor.extract_pdf_content.side_effect = Exception(
            "PDF parse error"
        )

        # Act & Assert
        with pytest.raises(Exception, match="PDF parse error"):
            await document_service.process_upload(
                document_id="doc-789",
                ticker="600519.SH",
                file_name="bad.pdf",
                file_path="/uploads/bad.pdf",
                pdf_bytes=b"not a pdf",
            )

        # Assert: status was set to failed
        status_calls = mock_document_repo.update_status.call_args_list
        statuses = [call[0][1] for call in status_calls]
        assert "processing" in statuses
        assert "failed" in statuses

    @pytest.mark.asyncio
    async def test_process_upload_returns_chunk_count(
        self,
        document_service: DocumentService,
        mock_pdf_processor: MagicMock,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload returns correct chunk_count from child chunks."""
        # Arrange
        child_chunks = [_make_child_chunk(f"c{i}") for i in range(5)]
        _setup_repo_mocks(mock_document_repo)
        mock_pdf_processor.extract_pdf_content.return_value = [
            {"type": "text", "content": "text", "page": 1, "bbox": (0, 0, 1, 1)},
        ]
        mock_pdf_processor.chunk_into_parents.return_value = [_make_parent_chunk()]
        mock_pdf_processor.chunk_parents_into_children.return_value = child_chunks
        mock_vector_store.upsert_chunks = AsyncMock()

        # Act
        result = await document_service.process_upload(
            document_id="doc-count",
            ticker="600519.SH",
            file_name="report.pdf",
            file_path="/uploads/report.pdf",
            pdf_bytes=b"%PDF content",
        )

        # Assert
        assert result.chunk_count == 5

    @pytest.mark.asyncio
    async def test_process_upload_returns_page_count(
        self,
        document_service: DocumentService,
        mock_pdf_processor: MagicMock,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload returns page_count from extracted content."""
        # Arrange
        content_blocks = [
            {"type": "text", "content": "Page 1", "page": 1, "bbox": (0, 0, 1, 1)},
            {"type": "text", "content": "Page 2", "page": 2, "bbox": (0, 0, 1, 1)},
            {"type": "text", "content": "Page 3", "page": 3, "bbox": (0, 0, 1, 1)},
        ]
        _setup_repo_mocks(mock_document_repo)
        mock_pdf_processor.extract_pdf_content.return_value = content_blocks
        mock_pdf_processor.chunk_into_parents.return_value = [_make_parent_chunk()]
        mock_pdf_processor.chunk_parents_into_children.return_value = [
            _make_child_chunk()
        ]
        mock_vector_store.upsert_chunks = AsyncMock()

        # Act
        result = await document_service.process_upload(
            document_id="doc-pages",
            ticker="600519.SH",
            file_name="report.pdf",
            file_path="/uploads/report.pdf",
            pdf_bytes=b"%PDF content",
        )

        # Assert
        assert result.page_count == 3


class TestGetDocumentStatus:
    """Tests for get_document_status method."""

    @pytest.mark.asyncio
    async def test_get_document_status_found(
        self,
        document_service: DocumentService,
        mock_document_repo: AsyncMock,
    ) -> None:
        """get_document_status returns status and chunk count for existing doc."""
        # Arrange
        mock_doc = MagicMock()
        mock_doc.processing_status = "completed"
        mock_doc.page_count = 42
        mock_doc.metadata_ = {"chunk_count": 15}
        mock_document_repo.get_by_document_id = AsyncMock(return_value=mock_doc)

        # Act
        result = await document_service.get_document_status("doc-123")

        # Assert
        assert result is not None
        assert result["status"] == "completed"
        assert result["page_count"] == 42
        assert result["chunk_count"] == 15
        mock_document_repo.get_by_document_id.assert_called_once_with("doc-123")

    @pytest.mark.asyncio
    async def test_get_document_status_not_found(
        self,
        document_service: DocumentService,
        mock_document_repo: AsyncMock,
    ) -> None:
        """get_document_status returns None for non-existent document."""
        # Arrange
        mock_document_repo.get_by_document_id = AsyncMock(return_value=None)

        # Act
        result = await document_service.get_document_status("nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_document_status_no_chunk_count_metadata(
        self,
        document_service: DocumentService,
        mock_document_repo: AsyncMock,
    ) -> None:
        """get_document_status handles document without chunk_count in metadata."""
        # Arrange
        mock_doc = MagicMock()
        mock_doc.processing_status = "processing"
        mock_doc.page_count = 10
        mock_doc.metadata_ = {}
        mock_document_repo.get_by_document_id = AsyncMock(return_value=mock_doc)

        # Act
        result = await document_service.get_document_status("doc-no-chunks")

        # Assert
        assert result is not None
        assert result["status"] == "processing"
        assert result["chunk_count"] == 0


class TestDeleteDocument:
    """Tests for delete_document method."""

    @pytest.mark.asyncio
    async def test_delete_document_removes_from_qdrant_and_db(
        self,
        document_service: DocumentService,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """delete_document removes chunks from Qdrant and record from DB."""
        # Arrange
        mock_doc = MagicMock()
        mock_doc.document_id = "doc-delete"
        mock_document_repo.get_by_document_id = AsyncMock(return_value=mock_doc)
        mock_document_repo.delete = AsyncMock(return_value=True)
        mock_vector_store.delete_by_document_id = MagicMock()

        # Act
        result = await document_service.delete_document("doc-delete")

        # Assert
        assert result is True
        mock_vector_store.delete_by_document_id.assert_called_once_with("doc-delete")
        mock_document_repo.delete.assert_called_once_with("doc-delete")

    @pytest.mark.asyncio
    async def test_delete_document_not_found(
        self,
        document_service: DocumentService,
        mock_document_repo: AsyncMock,
    ) -> None:
        """delete_document returns False when document does not exist."""
        # Arrange
        mock_document_repo.get_by_document_id = AsyncMock(return_value=None)

        # Act
        result = await document_service.delete_document("nonexistent")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_document_still_deletes_from_qdrant_on_db_error(
        self,
        document_service: DocumentService,
        mock_vector_store: AsyncMock,
        mock_document_repo: AsyncMock,
    ) -> None:
        """delete_document still removes Qdrant data even if DB delete fails."""
        # Arrange
        mock_doc = MagicMock()
        mock_doc.document_id = "doc-partial"
        mock_document_repo.get_by_document_id = AsyncMock(return_value=mock_doc)
        mock_document_repo.delete = AsyncMock(return_value=False)
        mock_vector_store.delete_by_document_id = MagicMock()

        # Act
        await document_service.delete_document("doc-partial")

        # Assert - Qdrant cleanup should still happen
        mock_vector_store.delete_by_document_id.assert_called_once_with("doc-partial")


class TestProcessUploadFileValidation:
    """Tests for file size validation in process_upload."""

    @pytest.mark.asyncio
    async def test_process_upload_rejects_oversized_file(
        self,
        document_service: DocumentService,
        mock_document_repo: AsyncMock,
    ) -> None:
        """process_upload rejects files exceeding max size limit."""
        # Arrange: create a "large" pdf (over 100MB)
        large_bytes = b"x" * (101 * 1024 * 1024)  # 101MB
        mock_document_repo.update_status = AsyncMock(return_value=MagicMock())

        # Act & Assert
        with pytest.raises(ValueError, match="File size exceeds"):
            await document_service.process_upload(
                document_id="doc-large",
                ticker="600519.SH",
                file_name="huge.pdf",
                file_path="/uploads/huge.pdf",
                pdf_bytes=large_bytes,
            )
