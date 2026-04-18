"""Tests for Qdrant vector store module.

Tests collection creation, upsert, search, and delete operations
using mocked Qdrant client.
"""

from unittest.mock import MagicMock, patch

from stockvaluefinder.models.document import ChunkMetadata, DocumentChunk
from stockvaluefinder.rag.vector_store import QdrantVectorStore


def _make_chunk(
    chunk_id: str = "chunk-1",
    content: str = "test content",
    chunk_type: str = "child",
    parent_id: str | None = "parent-1",
    ticker: str = "600519.SH",
    year: int = 2023,
    page_number: int = 1,
) -> DocumentChunk:
    """Helper to create a test DocumentChunk."""
    return DocumentChunk(
        chunk_id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            document_id="doc-1",
            parent_id=parent_id,
            page_number=page_number,
            section="financial_statements",
            ticker=ticker,
            year=year,
            report_type="annual",
            company_name="Test Corp",
            filing_date="2024-01-01",
            chunk_type=chunk_type,
            token_count=10,
        ),
    )


class TestQdrantVectorStoreInit:
    """Tests for QdrantVectorStore initialization."""

    def test_init_with_defaults(self) -> None:
        """Store initializes with default parameters."""
        store = QdrantVectorStore()

        assert store.url == "http://localhost:6333"
        assert store.collection == "annual_reports"
        assert store.api_key is None

    def test_init_with_custom_params(self) -> None:
        """Store initializes with custom parameters."""
        mock_embedding_client = MagicMock()
        store = QdrantVectorStore(
            url="http://custom:6333",
            collection="test_collection",
            api_key="secret",
            embedding_client=mock_embedding_client,
        )

        assert store.url == "http://custom:6333"
        assert store.collection == "test_collection"
        assert store.api_key == "secret"
        assert store.embedding_client is mock_embedding_client


class TestEnsureCollectionExists:
    """Tests for ensure_collection_exists method."""

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    def test_creates_collection_if_not_exists(self, mock_client_cls: MagicMock) -> None:
        """Collection is created when it does not exist."""
        mock_client = MagicMock()
        # get_collection raises to simulate not existing
        mock_client.get_collection.side_effect = Exception("not found")
        mock_client_cls.return_value = mock_client

        store = QdrantVectorStore()
        store.ensure_collection_exists()

        mock_client.create_collection.assert_called_once()

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    def test_creates_payload_indexes(self, mock_client_cls: MagicMock) -> None:
        """Payload indexes are created for ticker, year, report_type."""
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        mock_client_cls.return_value = mock_client

        store = QdrantVectorStore()
        store.ensure_collection_exists()

        # Should create indexes for ticker, year, report_type
        index_calls = mock_client.create_payload_index.call_args_list
        indexed_fields = {
            call.kwargs.get("field_name", call[1].get("field_name"))
            for call in index_calls
        }
        assert "ticker" in indexed_fields
        assert "year" in indexed_fields
        assert "report_type" in indexed_fields


class TestUpsertChunks:
    """Tests for upsert_chunks method."""

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    async def test_upsert_converts_chunks_to_points(
        self, mock_client_cls: MagicMock
    ) -> None:
        """Chunks are converted to PointStruct with vectors."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock embedding client
        mock_embedding = MagicMock()
        mock_embedding.generate_embeddings = MagicMock(
            return_value=[[0.1] * 1024, [0.2] * 1024]
        )

        async def mock_generate(texts: list[str]) -> list[list[float]]:
            return [[0.1] * 1024 for _ in texts]

        mock_embedding.generate_embeddings = mock_generate

        store = QdrantVectorStore(embedding_client=mock_embedding)
        chunks = [_make_chunk("c1"), _make_chunk("c2")]

        await store.upsert_chunks(chunks)

        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        points = call_args.kwargs.get("points", call_args[1].get("points", []))
        assert len(points) == 2

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    async def test_upsert_empty_list_is_noop(self, mock_client_cls: MagicMock) -> None:
        """Upserting empty list does not call Qdrant."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        store = QdrantVectorStore()
        await store.upsert_chunks([])

        mock_client.upsert.assert_not_called()


class TestSearch:
    """Tests for search method."""

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    async def test_search_returns_scored_chunks(
        self, mock_client_cls: MagicMock
    ) -> None:
        """Search returns list of scored chunks with payloads."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.85
        mock_result.payload = {
            "document_id": "doc-1",
            "parent_id": "parent-1",
            "page_number": 1,
            "content": "test content",
            "ticker": "600519.SH",
            "year": 2023,
        }
        mock_client.search.return_value = [mock_result]
        mock_client_cls.return_value = mock_client

        # Mock embedding client
        async def mock_generate(texts: list[str]) -> list[list[float]]:
            return [[0.5] * 1024 for _ in texts]

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = mock_generate

        store = QdrantVectorStore(embedding_client=mock_embedding)
        results = await store.search(
            query_vector=[0.5] * 1024,
            filter_dict={"ticker": "600519.SH"},
            limit=10,
            score_threshold=0.7,
        )

        assert len(results) == 1
        assert results[0]["score"] == 0.85
        mock_client.search.assert_called_once()

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    async def test_search_with_no_filter(self, mock_client_cls: MagicMock) -> None:
        """Search works without metadata filters."""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_client_cls.return_value = mock_client

        store = QdrantVectorStore()
        results = await store.search(
            query_vector=[0.5] * 1024,
        )

        assert isinstance(results, list)
        mock_client.search.assert_called_once()


class TestDeleteByDocumentId:
    """Tests for delete_by_document_id method."""

    @patch("stockvaluefinder.rag.vector_store.QdrantClient")
    def test_delete_calls_qdrant_filter(self, mock_client_cls: MagicMock) -> None:
        """Delete calls Qdrant with document_id filter."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        store = QdrantVectorStore()
        store.delete_by_document_id("doc-123")

        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert (
            call_args.kwargs.get("collection_name") == "annual_reports"
            or call_args[1].get("collection_name") == "annual_reports"
        )
