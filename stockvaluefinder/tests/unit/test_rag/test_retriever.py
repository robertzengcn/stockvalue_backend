"""Tests for semantic retriever module.

Tests search, multi-query expansion, parent context fetching,
and result aggregation/deduplication using mocked dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockvaluefinder.rag.retriever import SemanticRetriever, SearchResult


class TestSearchResult:
    """Tests for SearchResult frozen dataclass."""

    def test_search_result_is_frozen(self) -> None:
        """SearchResult is immutable after creation."""
        result = SearchResult(
            chunk_id="chunk-1",
            content="test content",
            parent_content="parent content",
            page_number=1,
            section="financial_statements",
            score=0.85,
            ticker="600519.SH",
            year=2023,
        )
        with pytest.raises(AttributeError):
            result.score = 0.9  # type: ignore[misc]

    def test_search_result_fields(self) -> None:
        """SearchResult has all required fields."""
        result = SearchResult(
            chunk_id="chunk-1",
            content="child content here",
            parent_content="parent context here",
            page_number=12,
            section="risk_factors",
            score=0.92,
            ticker="600519.SH",
            year=2023,
        )
        assert result.chunk_id == "chunk-1"
        assert result.content == "child content here"
        assert result.parent_content == "parent context here"
        assert result.page_number == 12
        assert result.section == "risk_factors"
        assert result.score == 0.92
        assert result.ticker == "600519.SH"
        assert result.year == 2023


class TestSemanticRetrieverInit:
    """Tests for SemanticRetriever initialization."""

    def test_init_stores_dependencies(self) -> None:
        """Retriever stores vector_store and embedding_client."""
        mock_store = MagicMock()
        mock_embedding = MagicMock()

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        assert retriever.vector_store is mock_store
        assert retriever.embedding_client is mock_embedding


class TestSearch:
    """Tests for the basic search method."""

    @pytest.mark.asyncio
    async def test_search_generates_query_embedding(self) -> None:
        """Search generates an embedding for the query string."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.1] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        await retriever.search(query="贵州茅台营业收入", ticker="600519.SH")

        mock_embedding.generate_query_embedding.assert_called_once_with(
            "贵州茅台营业收入"
        )

    @pytest.mark.asyncio
    async def test_search_calls_vector_store_with_filter(self) -> None:
        """Search passes metadata filter and query vector to vector store."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        await retriever.search(
            query="revenue growth",
            ticker="600519.SH",
            year=2023,
            limit=5,
            score_threshold=0.8,
        )

        mock_store.search.assert_called_once()
        call_kwargs = mock_store.search.call_args.kwargs
        assert call_kwargs["query_vector"] == [0.5] * 1024
        assert call_kwargs["filter_dict"]["ticker"] == "600519.SH"
        assert call_kwargs["filter_dict"]["year"] == 2023
        assert call_kwargs["filter_dict"]["chunk_type"] == "child"
        assert call_kwargs["limit"] == 5
        assert call_kwargs["score_threshold"] == 0.8

    @pytest.mark.asyncio
    async def test_search_returns_search_results(self) -> None:
        """Search returns list of SearchResult objects."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                {
                    "id": "child-1",
                    "score": 0.9,
                    "payload": {
                        "document_id": "doc-1",
                        "parent_id": "parent-1",
                        "page_number": 12,
                        "section": "financial_statements",
                        "ticker": "600519.SH",
                        "year": 2023,
                        "report_type": "annual",
                        "company_name": "Kweichow Moutai",
                        "filing_date": "2024-03-28",
                        "chunk_type": "child",
                        "token_count": 480,
                        "content": "Revenue was 100 billion yuan",
                    },
                },
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        # Mock fetch_parent_context by patching the internal method
        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        with patch.object(
            retriever,
            "fetch_parent_context",
            new_callable=AsyncMock,
            return_value="Parent document context with full financial details",
        ):
            results = await retriever.search(query="revenue", ticker="600519.SH")

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].chunk_id == "child-1"
        assert results[0].score == 0.9
        assert results[0].content == "Revenue was 100 billion yuan"
        assert results[0].page_number == 12
        assert results[0].section == "financial_statements"
        assert results[0].ticker == "600519.SH"
        assert results[0].year == 2023

    @pytest.mark.asyncio
    async def test_search_without_year_filter(self) -> None:
        """Search works with only ticker filter, no year."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        await retriever.search(query="risk factors", ticker="600519.SH")

        call_kwargs = mock_store.search.call_args.kwargs
        assert "ticker" in call_kwargs["filter_dict"]
        assert "year" not in call_kwargs["filter_dict"]

    @pytest.mark.asyncio
    async def test_search_without_ticker_filter(self) -> None:
        """Search works with no filters at all."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        await retriever.search(query="general query")

        call_kwargs = mock_store.search.call_args.kwargs
        # Only chunk_type filter should be present
        assert call_kwargs["filter_dict"]["chunk_type"] == "child"
        assert "ticker" not in call_kwargs["filter_dict"]

    @pytest.mark.asyncio
    async def test_search_parent_content_none_when_no_parent(self) -> None:
        """Search result has empty parent_content when parent not found."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                {
                    "id": "child-orphan",
                    "score": 0.75,
                    "payload": {
                        "document_id": "doc-1",
                        "parent_id": None,
                        "page_number": 5,
                        "section": "overview",
                        "ticker": "600519.SH",
                        "year": 2023,
                        "content": "Some content",
                    },
                },
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        results = await retriever.search(query="test", ticker="600519.SH")

        assert len(results) == 1
        assert results[0].parent_content == ""


class TestSearchWithMultiQueryExpansion:
    """Tests for multi-query expansion search."""

    @pytest.mark.asyncio
    async def test_generates_query_variations_via_llm(self) -> None:
        """Multi-query expansion calls LLM to generate variations."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        mock_llm = AsyncMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = (
            '["revenue growth rate", "营业收入增速", "sales increase percentage"]'
        )
        mock_llm.ainvoke.return_value = mock_llm_response

        with patch.object(retriever, "_get_llm", return_value=mock_llm):
            await retriever.search_with_multi_query_expansion(
                query="revenue growth",
                ticker="600519.SH",
                num_variations=3,
            )

        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_searches_each_variation(self) -> None:
        """Each query variation triggers a separate search."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        mock_llm = AsyncMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = (
            '["revenue growth", "营业收入增长", "sales increase"]'
        )
        mock_llm.ainvoke.return_value = mock_llm_response

        with patch.object(retriever, "_get_llm", return_value=mock_llm):
            await retriever.search_with_multi_query_expansion(
                query="revenue growth",
                ticker="600519.SH",
                num_variations=3,
            )

        # Original query + 3 variations = 4 searches
        assert mock_store.search.call_count == 4

    @pytest.mark.asyncio
    async def test_deduplicates_by_chunk_id(self) -> None:
        """Results with same chunk_id are deduplicated, keeping highest score."""
        mock_store = MagicMock()

        # Same chunk appears in multiple searches with different scores
        result_a = {
            "id": "chunk-1",
            "score": 0.85,
            "payload": {
                "document_id": "doc-1",
                "parent_id": "parent-1",
                "page_number": 5,
                "section": "overview",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "Content A",
            },
        }
        result_b = {
            "id": "chunk-1",
            "score": 0.92,
            "payload": {
                "document_id": "doc-1",
                "parent_id": "parent-1",
                "page_number": 5,
                "section": "overview",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "Content A",
            },
        }
        result_c = {
            "id": "chunk-2",
            "score": 0.78,
            "payload": {
                "document_id": "doc-1",
                "parent_id": "parent-2",
                "page_number": 10,
                "section": "risk",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "Content B",
            },
        }

        # First search (original), second search (var 1), third (var 2)
        mock_store.search = AsyncMock(
            side_effect=[
                [result_a],  # original query finds chunk-1 at 0.85
                [result_b],  # variation finds chunk-1 at 0.92
                [result_c],  # variation finds chunk-2 at 0.78
                [],  # variation finds nothing
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        mock_llm = AsyncMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = '["var1", "var2", "var3"]'
        mock_llm.ainvoke.return_value = mock_llm_response

        with patch.object(retriever, "_get_llm", return_value=mock_llm):
            with patch.object(
                retriever,
                "fetch_parent_context",
                new_callable=AsyncMock,
                return_value="parent content",
            ):
                results = await retriever.search_with_multi_query_expansion(
                    query="revenue growth",
                    ticker="600519.SH",
                    num_variations=3,
                )

        # chunk-1 deduplicated (highest score 0.92 kept), chunk-2 unique
        assert len(results) == 2
        # Results sorted by score descending
        assert results[0].score == 0.92
        assert results[0].chunk_id == "chunk-1"
        assert results[1].score == 0.78
        assert results[1].chunk_id == "chunk-2"

    @pytest.mark.asyncio
    async def test_falls_back_to_basic_search_on_llm_failure(self) -> None:
        """When LLM fails, falls back to basic single-query search."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        with patch.object(retriever, "_get_llm", return_value=None):
            results = await retriever.search_with_multi_query_expansion(
                query="revenue",
                ticker="600519.SH",
                num_variations=3,
            )

        # Falls back to basic search (single search call)
        assert mock_store.search.call_count == 1
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_descending(self) -> None:
        """Aggregated results are sorted by score descending."""
        mock_store = MagicMock()

        result_high = {
            "id": "chunk-high",
            "score": 0.95,
            "payload": {
                "parent_id": "p1",
                "page_number": 1,
                "section": "s1",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "high score",
            },
        }
        result_low = {
            "id": "chunk-low",
            "score": 0.70,
            "payload": {
                "parent_id": "p2",
                "page_number": 2,
                "section": "s2",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "low score",
            },
        }
        result_mid = {
            "id": "chunk-mid",
            "score": 0.82,
            "payload": {
                "parent_id": "p3",
                "page_number": 3,
                "section": "s3",
                "ticker": "600519.SH",
                "year": 2023,
                "content": "mid score",
            },
        }

        mock_store.search = AsyncMock(
            side_effect=[
                [result_high, result_mid],
                [result_low],
                [],
                [],
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        mock_llm = AsyncMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = '["var1", "var2", "var3"]'
        mock_llm.ainvoke.return_value = mock_llm_response

        with patch.object(retriever, "_get_llm", return_value=mock_llm):
            with patch.object(
                retriever,
                "fetch_parent_context",
                new_callable=AsyncMock,
                return_value="parent",
            ):
                results = await retriever.search_with_multi_query_expansion(
                    query="test",
                    ticker="600519.SH",
                    num_variations=3,
                )

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self) -> None:
        """Results are truncated to the specified limit."""
        mock_store = MagicMock()

        # Generate 5 results across searches
        results_batch = [
            {
                "id": f"chunk-{i}",
                "score": 0.8 - i * 0.05,
                "payload": {
                    "parent_id": f"p{i}",
                    "page_number": i,
                    "section": "s",
                    "ticker": "600519.SH",
                    "year": 2023,
                    "content": f"content {i}",
                },
            }
            for i in range(5)
        ]

        mock_store.search = AsyncMock(
            side_effect=[
                results_batch[:3],
                results_batch[3:],
                [],
                [],
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        mock_llm = AsyncMock()
        mock_llm_response = MagicMock()
        mock_llm_response.content = '["var1", "var2", "var3"]'
        mock_llm.ainvoke.return_value = mock_llm_response

        with patch.object(retriever, "_get_llm", return_value=mock_llm):
            with patch.object(
                retriever,
                "fetch_parent_context",
                new_callable=AsyncMock,
                return_value="parent",
            ):
                results = await retriever.search_with_multi_query_expansion(
                    query="test",
                    ticker="600519.SH",
                    limit=3,
                    num_variations=3,
                )

        assert len(results) <= 3


class TestFetchParentContext:
    """Tests for fetch_parent_context method."""

    @pytest.mark.asyncio
    async def test_queries_qdrant_for_parent_chunk(self) -> None:
        """fetch_parent_context searches Qdrant for parent chunk by ID."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                {
                    "id": "parent-1",
                    "score": 1.0,
                    "payload": {
                        "content": "Full parent context with detailed information",
                        "chunk_type": "parent",
                        "document_id": "doc-1",
                        "parent_id": None,
                        "page_number": 10,
                        "section": "financial_statements",
                        "ticker": "600519.SH",
                        "year": 2023,
                    },
                }
            ]
        )

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        result = await retriever.fetch_parent_context("parent-1")

        assert result == "Full parent context with detailed information"
        mock_store.search.assert_called_once()
        call_kwargs = mock_store.search.call_args.kwargs
        assert call_kwargs["filter_dict"]["chunk_type"] == "parent"

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_parent_found(self) -> None:
        """fetch_parent_context returns empty string when parent not found."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.generate_query_embedding = AsyncMock(return_value=[0.5] * 1024)

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        result = await retriever.fetch_parent_context("nonexistent-parent")

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_string_for_none_parent_id(self) -> None:
        """fetch_parent_context handles None parent_id gracefully."""
        mock_store = MagicMock()

        mock_embedding = MagicMock()

        retriever = SemanticRetriever(
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        result = await retriever.fetch_parent_context(None)

        assert result == ""
        mock_store.search.assert_not_called()
