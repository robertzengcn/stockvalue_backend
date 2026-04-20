"""Qdrant vector store for RAG pipeline document chunks.

Manages a single Qdrant collection with 1024-dim COSINE vectors,
payload indexes for metadata filtering (ticker, year, report_type),
and CRUD operations for document chunks.
"""

import logging
from dataclasses import asdict
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from stockvaluefinder.models.document import DocumentChunk
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Vector store backed by Qdrant for document chunk storage and retrieval.

    Stores child chunks with their embedding vectors and metadata payloads.
    Supports filtered semantic search with score thresholds.

    Attributes:
        url: Qdrant server URL.
        collection: Collection name for document chunks.
        api_key: Optional API key for Qdrant Cloud (None for self-hosted).
        embedding_client: Client for generating embedding vectors.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection: str = "annual_reports",
        api_key: str | None = None,
        embedding_client: BGEEmbeddingClient | None = None,
    ) -> None:
        """Initialize the Qdrant vector store.

        Args:
            url: Qdrant server URL.
            collection: Collection name for storing document chunks.
            api_key: Optional API key (for Qdrant Cloud).
            embedding_client: Client for generating embedding vectors.
        """
        self.url = url
        self.collection = collection
        self.api_key = api_key
        self.embedding_client = embedding_client or BGEEmbeddingClient()
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Lazy-initialize and return the Qdrant client.

        Returns:
            Configured QdrantClient instance.
        """
        if self._client is None:
            self._client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                check_compatibility=False,
            )
        return self._client

    def ensure_collection_exists(self) -> None:
        """Create the collection and payload indexes if they do not exist.

        Creates a collection with 1024-dim COSINE distance vectors and
        payload indexes on ticker (keyword), year (integer), and
        report_type (keyword) for efficient filtered search.
        """
        try:
            self.client.get_collection(self.collection)
            logger.info("Collection '%s' already exists", self.collection)
            return
        except Exception:
            logger.info("Creating collection '%s'", self.collection)

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

        # Create payload indexes for filtered search
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="ticker",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="year",
            field_schema=PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="report_type",
            field_schema=PayloadSchemaType.KEYWORD,
        )

        logger.info("Collection '%s' created with payload indexes", self.collection)

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Convert chunks to Qdrant points and upsert them.

        Generates embedding vectors for chunk content, then upserts
        each chunk as a PointStruct with its vector and metadata payload.

        Args:
            chunks: List of DocumentChunk objects to store.
        """
        if not chunks:
            return

        # Generate embeddings for all chunks
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_client.generate_embeddings(texts)

        # Build PointStruct list
        points: list[PointStruct] = []
        for chunk, embedding in zip(chunks, embeddings):
            payload = asdict(chunk.metadata)
            payload["content"] = chunk.content
            points.append(
                PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # Batch upsert
        self.client.upsert(
            collection_name=self.collection,
            points=points,
        )

        logger.info("Upserted %d chunks into '%s'", len(points), self.collection)

    async def search(
        self,
        query_vector: list[float],
        filter_dict: dict[str, Any] | None = None,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks using a query vector.

        Performs semantic search with optional metadata filtering and
        score threshold.

        Args:
            query_vector: 1024-dim query embedding vector.
            filter_dict: Optional metadata filters (e.g., {"ticker": "600519.SH"}).
            limit: Maximum number of results to return.
            score_threshold: Minimum similarity score (0.0-1.0).

        Returns:
            List of result dicts with id, score, and payload fields.
        """
        # Build filter conditions
        qdrant_filter = self._build_filter(filter_dict)

        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        results = response.points

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    def delete_by_document_id(self, document_id: str) -> None:
        """Delete all chunks belonging to a specific document.

        Args:
            document_id: The document ID to delete chunks for.
        """
        from qdrant_client.models import Filter as QdrantFilter

        self.client.delete(
            collection_name=self.collection,
            points_selector=QdrantFilter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )

        logger.info(
            "Deleted chunks for document '%s' from '%s'",
            document_id,
            self.collection,
        )

    def _build_filter(self, filter_dict: dict[str, Any] | None) -> Filter | None:
        """Build a Qdrant Filter from a plain dict.

        Args:
            filter_dict: Dict of field-value pairs for filtering.

        Returns:
            Qdrant Filter object or None if no filters specified.
        """
        if not filter_dict:
            return None

        conditions: list[FieldCondition] = []
        for field, value in filter_dict.items():
            conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))

        return Filter(must=conditions)


__all__ = [
    "QdrantVectorStore",
]
