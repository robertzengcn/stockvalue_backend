"""Tests for BGE embedding client.

Tests embedding generation via OpenRouter API with mocking.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.utils.errors import ExternalAPIError


class TestBGEEmbeddingClientInit:
    """Tests for BGEEmbeddingClient initialization."""

    def test_init_with_defaults(self) -> None:
        """Client initializes with default parameters."""
        client = BGEEmbeddingClient()

        assert client.api_url == "https://openrouter.ai/api/v1/embeddings"
        assert client.model == "baai/bge-m3"
        assert client.batch_size == 32

    def test_init_with_custom_params(self) -> None:
        """Client initializes with custom parameters."""
        client = BGEEmbeddingClient(
            api_url="https://custom.api/embeddings",
            api_key_env="CUSTOM_API_KEY",
            model="custom/model",
            batch_size=16,
        )

        assert client.api_url == "https://custom.api/embeddings"
        assert client.api_key_env == "CUSTOM_API_KEY"
        assert client.model == "custom/model"
        assert client.batch_size == 16


class TestGenerateEmbeddings:
    """Tests for generate_embeddings method."""

    @pytest.mark.asyncio
    async def test_returns_list_of_float_lists(self) -> None:
        """generate_embeddings returns list[list[float]]."""
        client = BGEEmbeddingClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1024},
                {"embedding": [0.2] * 1024},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await client.generate_embeddings(["hello", "world"])

        assert isinstance(result, list)
        assert len(result) == 2
        for emb in result:
            assert isinstance(emb, list)
            assert len(emb) == 1024
            assert all(isinstance(v, float) for v in emb)

    @pytest.mark.asyncio
    async def test_api_call_uses_correct_headers(self) -> None:
        """API call includes Authorization and Content-Type headers."""
        client = BGEEmbeddingClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "my-secret-key"}):
                await client.generate_embeddings(["test"])

            call_kwargs = mock_http.post.call_args
            headers = call_kwargs.kwargs.get(
                "headers", call_kwargs[1].get("headers", {})
            )
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer my-secret-key"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_api_call_sends_model_and_input(self) -> None:
        """API call sends correct model name and input texts."""
        client = BGEEmbeddingClient(model="baai/bge-m3")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                await client.generate_embeddings(["hello world"])

            call_kwargs = mock_http.post.call_args
            json_body = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert json_body["model"] == "baai/bge-m3"
            assert json_body["input"] == ["hello world"]

    @pytest.mark.asyncio
    async def test_batch_splitting(self) -> None:
        """Large input lists are split into batches."""
        client = BGEEmbeddingClient(batch_size=2)

        # Create different mock responses for each batch
        resp_batch1 = MagicMock()
        resp_batch1.status_code = 200
        resp_batch1.json.return_value = {
            "data": [{"embedding": [0.1] * 1024}, {"embedding": [0.2] * 1024}]
        }
        resp_batch1.raise_for_status = MagicMock()

        resp_batch2 = MagicMock()
        resp_batch2.status_code = 200
        resp_batch2.json.return_value = {
            "data": [{"embedding": [0.3] * 1024}, {"embedding": [0.4] * 1024}]
        }
        resp_batch2.raise_for_status = MagicMock()

        resp_batch3 = MagicMock()
        resp_batch3.status_code = 200
        resp_batch3.json.return_value = {"data": [{"embedding": [0.5] * 1024}]}
        resp_batch3.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=[resp_batch1, resp_batch2, resp_batch3]
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await client.generate_embeddings(["a", "b", "c", "d", "e"])

        # 5 texts with batch_size=2 = 3 API calls (2+2+1)
        assert mock_http.post.call_count == 3
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self) -> None:
        """Missing API key raises ExternalAPIError."""
        client = BGEEmbeddingClient()

        with patch.dict(os.environ, {}, clear=False):
            # Remove OPENROUTER_API_KEY if it exists
            env = os.environ.copy()
            env.pop("OPENROUTER_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ExternalAPIError, match="API key"):
                    await client.generate_embeddings(["test"])


class TestGenerateQueryEmbedding:
    """Tests for generate_query_embedding method."""

    @pytest.mark.asyncio
    async def test_returns_single_vector(self) -> None:
        """generate_query_embedding returns a single vector."""
        client = BGEEmbeddingClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1024}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await client.generate_query_embedding("search query")

        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_sends_single_text(self) -> None:
        """generate_query_embedding sends a single-item list."""
        client = BGEEmbeddingClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1024}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                await client.generate_query_embedding("my query")

            call_kwargs = mock_http.post.call_args
            json_body = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert json_body["input"] == ["my query"]


class TestRetryBehavior:
    """Tests for retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retries_on_429(self) -> None:
        """Client retries on 429 status code."""
        import httpx

        client = BGEEmbeddingClient()

        error_response_429 = MagicMock()
        error_response_429.status_code = 429
        error_response_429.text = "Rate limited"
        http_error_429 = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=error_response_429
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
        success_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            # First call raises 429, second succeeds
            mock_http.post = AsyncMock(side_effect=[http_error_429, success_response])
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await client.generate_embeddings(["test"])

        assert len(result) == 1
        assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_503(self) -> None:
        """Client retries on 503 status code."""
        import httpx

        client = BGEEmbeddingClient(max_retries=2)

        error_response_503 = MagicMock()
        error_response_503.status_code = 503
        error_response_503.text = "Service unavailable"
        http_error_503 = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=error_response_503
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
        success_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=[http_error_503, success_response])
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await client.generate_embeddings(["test"])

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """Client raises error after max retries exhausted."""
        import httpx

        client = BGEEmbeddingClient(max_retries=1)

        error_response = MagicMock()
        error_response.status_code = 429
        error_response.text = "Rate limited"
        http_error = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=error_response
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=http_error)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with pytest.raises(ExternalAPIError, match="attempts"):
                        await client.generate_embeddings(["test"])
