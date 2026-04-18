"""BGE-M3 embedding client via OpenRouter API.

Generates 1024-dimensional vectors for Chinese and English financial text
using the bge-m3 model through an OpenAI-compatible API endpoint.
Supports batch processing with automatic chunking and retry with
exponential backoff on rate-limit/server errors.
"""

import asyncio
import logging
import math
import os

import httpx

from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class BGEEmbeddingClient:
    """Client for generating bge-m3 embeddings via OpenRouter API.

    Uses httpx.AsyncClient for non-blocking HTTP calls. API key is read
    from an environment variable for secure credential management.

    Attributes:
        api_url: Embedding API endpoint URL.
        api_key_env: Name of the environment variable holding the API key.
        model: Model identifier for the embedding API.
        batch_size: Maximum number of texts per API call.
        max_retries: Maximum retry attempts on transient errors.
    """

    def __init__(
        self,
        api_url: str = "https://openrouter.ai/api/v1/embeddings",
        api_key_env: str = "OPENROUTER_API_KEY",
        model: str = "baai/bge-m3",
        batch_size: int = 32,
        max_retries: int = 3,
    ) -> None:
        """Initialize the embedding client.

        Args:
            api_url: Embedding API endpoint URL.
            api_key_env: Environment variable name for the API key.
            model: Model identifier for the embedding API.
            batch_size: Maximum number of texts per API call.
            max_retries: Maximum retry attempts on transient errors.
        """
        self.api_url = api_url
        self.api_key_env = api_key_env
        self.model = model
        self.batch_size = batch_size
        self.max_retries = max_retries

    def _get_api_key(self) -> str:
        """Read API key from environment variable.

        Returns:
            API key string.

        Raises:
            ExternalAPIError: If the API key is not set.
        """
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ExternalAPIError(
                f"API key not found in environment variable: {self.api_key_env}",
                service="embedding",
            )
        return api_key

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Splits texts into batches of ``batch_size`` and makes one API call
        per batch. Results are concatenated in order.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of 1024-dimensional float vectors, one per input text.

        Raises:
            ExternalAPIError: If the API key is missing or all retries fail.
        """
        api_key = self._get_api_key()
        all_embeddings: list[list[float]] = []

        # Split into batches
        num_batches = math.ceil(len(texts) / self.batch_size)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(num_batches):
                start = i * self.batch_size
                end = min(start + self.batch_size, len(texts))
                batch = texts[start:end]

                batch_embeddings = await self._call_with_retry(client, batch, api_key)
                all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Convenience method for single-text embedding generation.

        Args:
            query: The search query text to embed.

        Returns:
            A single 1024-dimensional float vector.

        Raises:
            ExternalAPIError: If the API key is missing or all retries fail.
        """
        results = await self.generate_embeddings([query])
        return results[0]

    async def _call_with_retry(
        self,
        client: httpx.AsyncClient,
        texts: list[str],
        api_key: str,
    ) -> list[list[float]]:
        """Make an API call with exponential backoff retry.

        Retries on HTTP 429 (rate limit) and 503 (service unavailable).

        Args:
            client: httpx async client to use for the request.
            texts: List of texts to send in this batch.
            api_key: API key for authorization.

        Returns:
            List of embedding vectors from the API response.

        Raises:
            ExternalAPIError: If all retry attempts are exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": texts,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in (429, 503) and attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "Embedding API returned %d, retrying in %ds (attempt %d/%d)",
                        status_code,
                        wait_time,
                        attempt + 1,
                        self.max_retries,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ExternalAPIError(
                    f"Embedding API error after {attempt + 1} attempts: {exc}",
                    service="embedding",
                    status_code=status_code,
                ) from exc

            except httpx.RequestError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "Embedding API request failed: %s, retrying in %ds",
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ExternalAPIError(
                    f"Embedding API request failed after {attempt + 1} attempts: {exc}",
                    service="embedding",
                ) from exc

        # Should not reach here, but just in case
        raise ExternalAPIError(
            f"Embedding API failed after {self.max_retries} retries",
            service="embedding",
        ) from last_error


__all__ = [
    "BGEEmbeddingClient",
]
