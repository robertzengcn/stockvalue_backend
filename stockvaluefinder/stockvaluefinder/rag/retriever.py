"""Semantic retriever for RAG pipeline document search.

Provides single-query and multi-query expansion search over Qdrant
vector store with parent-child document pairing. Returns structured
SearchResult objects with child content, parent context, page references,
and relevance scores.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

# Prompt template for generating query variations
_MULTI_QUERY_PROMPT = """You are an AI assistant that generates alternative search queries for financial document retrieval.

Given the original query, generate {num_variations} alternative queries that capture the same information need using different phrasings, synonyms, or languages (Chinese/English mix is acceptable for financial terms).

Original query: {query}

Return ONLY a JSON array of strings, no other text.
Example: ["alternative query 1", "alternative query 2", "alternative query 3"]"""


@dataclass(frozen=True)
class SearchResult:
    """A single search result from semantic retrieval.

    Attributes:
        chunk_id: Unique identifier of the matched child chunk.
        content: Text content of the matched child chunk.
        parent_content: Full text content of the parent chunk (broader context).
        page_number: Original page number in the PDF (1-based).
        section: Document section heading (e.g., "financial_statements").
        score: Cosine similarity score (0.0-1.0).
        ticker: Stock ticker this result belongs to.
        year: Fiscal year of the source document.
    """

    chunk_id: str
    content: str
    parent_content: str
    page_number: int
    section: str
    score: float
    ticker: str
    year: int


class SemanticRetriever:
    """Semantic retriever with optional multi-query expansion.

    Performs semantic search over document chunks stored in Qdrant,
    retrieves parent context for each child match, and supports
    LLM-powered multi-query expansion for improved recall.

    Attributes:
        vector_store: QdrantVectorStore for vector similarity search.
        embedding_client: BGEEmbeddingClient for query embedding generation.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        embedding_client: BGEEmbeddingClient | None = None,
    ) -> None:
        """Initialize the semantic retriever.

        Args:
            vector_store: QdrantVectorStore instance for searching.
            embedding_client: Optional embedding client. If None, creates
                a default BGEEmbeddingClient.
        """
        self.vector_store = vector_store
        self.embedding_client = embedding_client or BGEEmbeddingClient()
        self._llm: Any = None
        self._llm_initialized: bool = False

    def _get_llm(self) -> Any:
        """Lazily initialize and return the LLM client.

        Returns None if initialization fails (missing API key, etc).

        Returns:
            LangChain LLM client or None on failure.
        """
        if not self._llm_initialized:
            try:
                from stockvaluefinder.llm_factory import create_llm

                self._llm = create_llm(provider="deepseek")
                self._llm_initialized = True
            except Exception:
                logger.warning(
                    "LLM initialization failed; multi-query expansion disabled",
                    exc_info=True,
                )
                self._llm = None
                self._llm_initialized = True
        return self._llm

    async def search(
        self,
        query: str,
        ticker: str | None = None,
        year: int | None = None,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Search for semantically similar document chunks.

        Generates an embedding for the query, performs filtered search
        against the vector store, and enriches each result with parent
        context.

        Args:
            query: Search query text.
            ticker: Optional ticker filter (e.g., "600519.SH").
            year: Optional fiscal year filter.
            limit: Maximum number of results to return.
            score_threshold: Minimum similarity score (0.0-1.0).

        Returns:
            List of SearchResult objects sorted by score descending.
        """
        query_vector = await self.embedding_client.generate_query_embedding(query)

        filter_dict = self._build_filter(ticker=ticker, year=year)
        raw_results = await self.vector_store.search(
            query_vector=query_vector,
            filter_dict=filter_dict,
            limit=limit,
            score_threshold=score_threshold,
        )

        return await self._enrich_results(raw_results)

    async def search_with_multi_query_expansion(
        self,
        query: str,
        ticker: str | None = None,
        year: int | None = None,
        limit: int = 10,
        score_threshold: float = 0.7,
        num_variations: int = 3,
    ) -> list[SearchResult]:
        """Search with multi-query expansion for improved recall.

        Uses LLM to generate query variations, searches with each
        variation, aggregates results, deduplicates by chunk_id
        keeping the highest score, and returns sorted results.

        Falls back to basic search if LLM is unavailable.

        Args:
            query: Original search query text.
            ticker: Optional ticker filter.
            year: Optional fiscal year filter.
            limit: Maximum number of results to return.
            score_threshold: Minimum similarity score.
            num_variations: Number of query variations to generate (3-5).

        Returns:
            Deduplicated list of SearchResult objects sorted by score.
        """
        llm = self._get_llm()

        if llm is None:
            logger.info("LLM unavailable, falling back to basic search")
            return await self.search(
                query=query,
                ticker=ticker,
                year=year,
                limit=limit,
                score_threshold=score_threshold,
            )

        # Generate query variations via LLM
        variations = await self._generate_query_variations(llm, query, num_variations)

        # Collect all queries: original + variations
        all_queries = [query] + variations

        # Search with each query and collect raw results
        all_raw: list[dict[str, Any]] = []
        filter_dict = self._build_filter(ticker=ticker, year=year)

        for q in all_queries:
            query_vector = await self.embedding_client.generate_query_embedding(q)
            results = await self.vector_store.search(
                query_vector=query_vector,
                filter_dict=filter_dict,
                limit=limit,
                score_threshold=score_threshold,
            )
            all_raw.extend(results)

        # Deduplicate by chunk_id, keeping highest score
        deduped = self._deduplicate_results(all_raw)

        # Sort by score descending and apply limit
        deduped.sort(key=lambda r: r["score"], reverse=True)
        deduped = deduped[:limit]

        return await self._enrich_results(deduped)

    async def fetch_parent_context(self, parent_id: str | None) -> str:
        """Fetch the parent chunk content from the vector store.

        Searches Qdrant for a parent chunk by its ID and returns
        its content. Used to provide broader context for child matches.

        Args:
            parent_id: UUID of the parent chunk to fetch. If None,
                returns empty string immediately.

        Returns:
            Parent chunk content string, or empty string if not found.
        """
        if parent_id is None:
            return ""

        try:
            query_vector = await self.embedding_client.generate_query_embedding("")
            results = await self.vector_store.search(
                query_vector=query_vector,
                filter_dict={"chunk_type": "parent"},
                limit=100,
                score_threshold=0.0,
            )

            for result in results:
                if result["id"] == parent_id:
                    payload = result["payload"]
                    return payload.get("content", "")

            return ""

        except Exception:
            logger.warning(
                "Failed to fetch parent context for %s",
                parent_id,
                exc_info=True,
            )
            return ""

    def _build_filter(
        self,
        ticker: str | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Build metadata filter dict for vector store search.

        Always includes chunk_type=child to only search child chunks.
        Adds ticker and year filters if provided.

        Args:
            ticker: Optional stock ticker filter.
            year: Optional fiscal year filter.

        Returns:
            Dict of field-value pairs for Qdrant filtering.
        """
        filter_dict: dict[str, Any] = {"chunk_type": "child"}

        if ticker is not None:
            filter_dict["ticker"] = ticker
        if year is not None:
            filter_dict["year"] = year

        return filter_dict

    @staticmethod
    def _deduplicate_results(
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Deduplicate search results by chunk_id, keeping highest score.

        Args:
            results: List of raw result dicts with id, score, and payload.

        Returns:
            Deduplicated list of result dicts.
        """
        best_by_id: dict[str, dict[str, Any]] = {}
        for result in results:
            chunk_id = str(result.get("id", ""))
            if chunk_id not in best_by_id:
                best_by_id[chunk_id] = result
            else:
                existing_score = best_by_id[chunk_id].get("score", 0.0)
                new_score = result.get("score", 0.0)
                if new_score > existing_score:
                    best_by_id[chunk_id] = result
        return list(best_by_id.values())

    async def _enrich_results(
        self, raw_results: list[dict[str, Any]]
    ) -> list[SearchResult]:
        """Convert raw search results to SearchResult with parent context.

        For each raw result, extracts metadata and fetches parent content
        from the vector store.

        Args:
            raw_results: List of raw result dicts from vector store search.

        Returns:
            List of SearchResult objects with parent context.
        """
        search_results: list[SearchResult] = []

        for raw in raw_results:
            payload = raw.get("payload", {})
            parent_id = payload.get("parent_id")

            parent_content = await self.fetch_parent_context(parent_id)

            search_results.append(
                SearchResult(
                    chunk_id=str(raw.get("id", "")),
                    content=payload.get("content", ""),
                    parent_content=parent_content,
                    page_number=payload.get("page_number", 0),
                    section=payload.get("section", ""),
                    score=raw.get("score", 0.0),
                    ticker=payload.get("ticker", ""),
                    year=payload.get("year", 0),
                )
            )

        return search_results

    async def _generate_query_variations(
        self, llm: Any, query: str, num_variations: int
    ) -> list[str]:
        """Generate query variations using LLM.

        Args:
            llm: LangChain LLM client.
            query: Original search query.
            num_variations: Number of variations to generate.

        Returns:
            List of query variation strings.
        """
        from langchain_core.messages import HumanMessage

        prompt = _MULTI_QUERY_PROMPT.format(num_variations=num_variations, query=query)

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            return self._parse_query_variations(content)
        except Exception:
            logger.warning("LLM query variation generation failed", exc_info=True)
            return []

    @staticmethod
    def _parse_query_variations(content: str) -> list[str]:
        """Parse LLM response into a list of query strings.

        Handles JSON array format, with fallback to extracting
        quoted strings from the response.

        Args:
            content: Raw LLM response text.

        Returns:
            List of query variation strings.
        """
        if not content or not content.strip():
            return []

        # Try parsing as JSON array
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(code_block_pattern, content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if isinstance(item, str)]
            except json.JSONDecodeError:
                pass

        # Fallback: extract quoted strings
        quoted_pattern = r'"([^"]+)"'
        matches = re.findall(quoted_pattern, content)
        if matches:
            return matches

        return []


__all__ = [
    "SemanticRetriever",
    "SearchResult",
]
