"""Unit tests for download_report worker function and helper functions.

Tests cover:
- Successful download with state transitions and document creation
- Rate limiting between requests
- Deduplication by source_id and content_hash
- Download failure with FAILED state transition
- Content-Type validation (reject HTML)
- Enqueue parse_report after successful download
- Missing task handling
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.pipeline.state import PipelineState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_db(
    task_id: str | None = None,
    ticker: str = "600519.SH",
    business_key: str = "600519.SH:2023:annual",
    state: str = "pending",
) -> MagicMock:
    """Create a mock PipelineTaskDB object."""
    task = MagicMock()
    task.task_id = task_id or str(uuid4())
    task.ticker = ticker
    task.business_key = business_key
    task.state = state
    return task


def _make_disclosure_db(
    ticker: str = "600519.SH",
    fiscal_year: int = 2023,
    report_type: str = "annual",
    source_raw: dict | None = None,
) -> MagicMock:
    """Create a mock PendingDisclosureDB object."""
    disclosure = MagicMock()
    disclosure.ticker = ticker
    disclosure.fiscal_year = fiscal_year
    disclosure.report_type = report_type
    disclosure.source_raw = source_raw or {
        "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?announcementId=abc123&orgId=990001"
    }
    return disclosure


def _make_mock_session_ctx() -> tuple[AsyncMock, MagicMock]:
    """Create a mock session and session_factory for worker context.

    Returns:
        Tuple of (mock_session, mock_session_factory).
    """
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.close = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_session, mock_session_factory


def _build_ctx(
    session_factory: MagicMock | None = None,
    http_client: AsyncMock | None = None,
) -> dict:
    """Build a worker context dict."""
    _, factory = _make_mock_session_ctx()
    return {
        "session_factory": session_factory or factory,
        "http_client": http_client or AsyncMock(),
    }


# ---------------------------------------------------------------------------
# _extract_pdf_url tests
# ---------------------------------------------------------------------------


class TestExtractPdfUrl:
    """Tests for _extract_pdf_url helper function."""

    def test_extracts_announcement_id_from_url(self) -> None:
        """_extract_pdf_url constructs PDF URL from announcementId query param."""
        from stockvaluefinder.pipeline.worker import _extract_pdf_url

        source_raw = {
            "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?announcementId=abc123&orgId=990001"
        }
        result = _extract_pdf_url(source_raw)
        assert result == "https://static.cninfo.com.cn/abc123.PDF"

    def test_returns_none_when_no_link(self) -> None:
        """_extract_pdf_url returns None when no announcement link."""
        from stockvaluefinder.pipeline.worker import _extract_pdf_url

        result = _extract_pdf_url({})
        assert result is None

    def test_returns_none_when_no_announcement_id(self) -> None:
        """_extract_pdf_url returns None when URL lacks announcementId."""
        from stockvaluefinder.pipeline.worker import _extract_pdf_url

        source_raw = {"公告链接": "http://www.cninfo.com.cn/some/other/path"}
        result = _extract_pdf_url(source_raw)
        assert result is None

    def test_returns_none_for_none_source_raw(self) -> None:
        """_extract_pdf_url returns None when source_raw is None."""
        from stockvaluefinder.pipeline.worker import _extract_pdf_url

        result = _extract_pdf_url(None)
        assert result is None


# ---------------------------------------------------------------------------
# _download_pdf tests
# ---------------------------------------------------------------------------


class TestDownloadPdf:
    """Tests for _download_pdf helper function."""

    @pytest.mark.asyncio
    async def test_downloads_and_hashes_pdf(self) -> None:
        """_download_pdf streams PDF, computes SHA256, returns bytes + hash."""
        from stockvaluefinder.pipeline.worker import _download_pdf

        pdf_content = b"%PDF-1.4 fake content"
        expected_hash = hashlib.sha256(pdf_content).hexdigest()

        # Mock streaming response
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        # aiter_bytes returns an async iterator directly (not a coroutine)
        mock_response.aiter_bytes = MagicMock(return_value=AsyncIterator([pdf_content]))

        mock_client = MagicMock()
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        pdf_bytes, hex_hash = await _download_pdf(
            mock_client, "https://example.com/test.pdf", 0.0
        )

        assert pdf_bytes == pdf_content
        assert hex_hash == expected_hash

    @pytest.mark.asyncio
    async def test_rejects_html_content_type(self) -> None:
        """_download_pdf raises when Content-Type is HTML."""
        from stockvaluefinder.pipeline.worker import _download_pdf

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = MagicMock(return_value=AsyncIterator([]))

        mock_client = MagicMock()
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        with pytest.raises(Exception, match="Expected PDF"):
            await _download_pdf(mock_client, "https://example.com/test.html", 0.0)

    @pytest.mark.asyncio
    async def test_rate_limiting_applies_delay(self) -> None:
        """_download_pdf sleeps for the configured delay before downloading."""
        from stockvaluefinder.pipeline.worker import _download_pdf

        pdf_content = b"%PDF-1.4"
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = MagicMock(return_value=AsyncIterator([pdf_content]))

        mock_client = MagicMock()
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        with patch(
            "stockvaluefinder.pipeline.worker.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await _download_pdf(mock_client, "https://example.com/test.pdf", 0.5)
            mock_sleep.assert_awaited_once_with(0.5)


# ---------------------------------------------------------------------------
# download_report integration tests
# ---------------------------------------------------------------------------


class TestDownloadReport:
    """Tests for the download_report worker function."""

    @pytest.mark.asyncio
    async def test_successful_download_transitions_states(self) -> None:
        """Successful download transitions PENDING->DOWNLOADING->PARSING."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()

        # Mock task repo
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        # Mock doc repo
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=None)
        mock_doc_repo.get_by_content_hash = AsyncMock(return_value=None)
        mock_doc_repo.create_document = AsyncMock(return_value=MagicMock())

        # Mock disclosure query
        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        # Mock httpx client
        pdf_content = b"%PDF-1.4 fake content"
        mock_http_client = self._create_mock_http_client(pdf_content)

        ctx = _build_ctx(
            session_factory=mock_session_factory,
            http_client=mock_http_client,
        )

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._download_pdf",
                new_callable=AsyncMock,
                return_value=(pdf_content, "abc123hash"),
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_parse",
                new_callable=AsyncMock,
            ),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_bytes"),
        ):
            await download_report(ctx, task_id)

        # Verify state transitions: DOWNLOADING then PARSING
        assert mock_task_repo.transition_state.call_count == 2
        first_call = mock_task_repo.transition_state.call_args_list[0]
        assert first_call[0][1] == PipelineState.DOWNLOADING

        second_call = mock_task_repo.transition_state.call_args_list[1]
        assert second_call[0][1] == PipelineState.PARSING

    @pytest.mark.asyncio
    async def test_creates_document_record_with_sha256(self) -> None:
        """Document record is created with SHA256 hash and file path."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=None)
        mock_doc_repo.get_by_content_hash = AsyncMock(return_value=None)
        mock_doc_repo.create_document = AsyncMock(return_value=MagicMock())

        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        pdf_content = b"%PDF-1.4 fake content"
        ctx = _build_ctx(session_factory=mock_session_factory)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._download_pdf",
                new_callable=AsyncMock,
                return_value=(pdf_content, "deadbeef" * 8),
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_parse",
                new_callable=AsyncMock,
            ),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_bytes"),
        ):
            await download_report(ctx, task_id)

        # Verify document was created with content hash
        mock_doc_repo.create_document.assert_awaited_once()
        call_kwargs = mock_doc_repo.create_document.call_args[1]
        assert call_kwargs["content_hash"] == "deadbeef" * 8
        assert call_kwargs["file_size"] == len(pdf_content)
        assert "600519.SH" in call_kwargs["file_path"]
        assert "2023" in call_kwargs["file_path"]

    @pytest.mark.asyncio
    async def test_dedup_by_source_id_skips_download(self) -> None:
        """Download skipped when source_id already exists in pipeline_documents."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        existing_doc = MagicMock()
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=existing_doc)
        mock_doc_repo.create_document = AsyncMock()

        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        mock_download = AsyncMock(return_value=(b"pdf", "hash"))
        ctx = _build_ctx(session_factory=mock_session_factory)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch("stockvaluefinder.pipeline.worker._download_pdf", mock_download),
            patch(
                "stockvaluefinder.pipeline.worker._extract_pdf_url",
                return_value="https://static.cninfo.com.cn/abc123.PDF",
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_parse",
                new_callable=AsyncMock,
            ),
        ):
            await download_report(ctx, task_id)

        # _download_pdf should NOT have been called
        mock_download.assert_not_awaited()
        # No new document should be created
        mock_doc_repo.create_document.assert_not_awaited()
        # State should still transition to PARSING
        transitions = mock_task_repo.transition_state.call_args_list
        assert any(c[0][1] == PipelineState.PARSING for c in transitions)

    @pytest.mark.asyncio
    async def test_dedup_by_content_hash_skips_write(self) -> None:
        """File write skipped when content_hash already exists in pipeline_documents."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        existing_doc = MagicMock()
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=None)
        mock_doc_repo.get_by_content_hash = AsyncMock(return_value=existing_doc)
        mock_doc_repo.create_document = AsyncMock()

        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        ctx = _build_ctx(session_factory=mock_session_factory)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._download_pdf",
                new_callable=AsyncMock,
                return_value=(b"pdf", "abc123hash"),
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_parse",
                new_callable=AsyncMock,
            ),
        ):
            await download_report(ctx, task_id)

        # No new document should be created
        mock_doc_repo.create_document.assert_not_awaited()
        # State should still transition to PARSING
        transitions = mock_task_repo.transition_state.call_args_list
        assert any(c[0][1] == PipelineState.PARSING for c in transitions)

    @pytest.mark.asyncio
    async def test_download_failure_transitions_to_failed(self) -> None:
        """Task transitions to FAILED on download exception."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=None)

        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        ctx = _build_ctx(session_factory=mock_session_factory)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._download_pdf",
                new_callable=AsyncMock,
                side_effect=Exception("Connection timeout"),
            ),
            pytest.raises(Exception, match="Connection timeout"),
        ):
            await download_report(ctx, task_id)

        # Verify FAILED transition
        failed_calls = [
            c
            for c in mock_task_repo.transition_state.call_args_list
            if c[0][1] == PipelineState.FAILED
        ]
        assert len(failed_calls) == 1
        assert "Connection timeout" in failed_calls[0][1]["error_message"]

    @pytest.mark.asyncio
    async def test_returns_early_when_task_not_found(self) -> None:
        """download_report returns early when task_id not found in DB."""
        from stockvaluefinder.pipeline.worker import download_report

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=None)
        mock_task_repo.transition_state = AsyncMock()

        ctx = _build_ctx(session_factory=mock_session_factory)

        with patch(
            "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
            return_value=mock_task_repo,
        ):
            await download_report(ctx, "nonexistent-task-id")

        # No state transition should have been attempted
        mock_task_repo.transition_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueue_parse_after_success(self) -> None:
        """parse_report job enqueued after successful download."""
        from stockvaluefinder.pipeline.worker import download_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_source_id = AsyncMock(return_value=None)
        mock_doc_repo.get_by_content_hash = AsyncMock(return_value=None)
        mock_doc_repo.create_document = AsyncMock(return_value=MagicMock())

        mock_disclosure = _make_disclosure_db()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        pdf_content = b"%PDF-1.4"
        ctx = _build_ctx(session_factory=mock_session_factory)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._download_pdf",
                new_callable=AsyncMock,
                return_value=(pdf_content, "hash"),
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_parse",
                new_callable=AsyncMock,
            ) as mock_enqueue,
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_bytes"),
        ):
            await download_report(ctx, task_id)

        mock_enqueue.assert_awaited_once_with(task_id)

    def _create_mock_http_client(self, pdf_content: bytes) -> AsyncMock:
        """Create a mock httpx client with streaming support."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = AsyncMock(return_value=AsyncIterator([pdf_content]))

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        return mock_client


# ---------------------------------------------------------------------------
# _get_source_metadata tests
# ---------------------------------------------------------------------------


class TestGetSourceMetadata:
    """Tests for _get_source_metadata helper function."""

    @pytest.mark.asyncio
    async def test_extracts_metadata_from_disclosure(self) -> None:
        """_get_source_metadata returns source_id and source_raw from disclosure."""
        from stockvaluefinder.pipeline.worker import _get_source_metadata

        source_raw = {
            "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?announcementId=test123"
        }

        mock_disclosure = MagicMock()
        mock_disclosure.source_raw = source_raw

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        first=MagicMock(return_value=mock_disclosure)
                    )
                )
            )
        )

        task = _make_task_db(business_key="600519.SH:2023:annual")

        source_id, raw = await _get_source_metadata(mock_session, task)

        assert source_id == "test123"
        assert raw is source_raw

    @pytest.mark.asyncio
    async def test_returns_none_when_no_disclosure(self) -> None:
        """_get_source_metadata returns (None, None) when no disclosure found."""
        from stockvaluefinder.pipeline.worker import _get_source_metadata

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(first=MagicMock(return_value=None))
                )
            )
        )

        task = _make_task_db(business_key="600519.SH:2023:annual")

        source_id, raw = await _get_source_metadata(mock_session, task)

        assert source_id is None
        assert raw is None


# ---------------------------------------------------------------------------
# Helper: AsyncIterator for mocking aiter_bytes
# ---------------------------------------------------------------------------


class AsyncIterator:
    """Async iterator for test mocking."""

    def __init__(self, items: list) -> None:
        self._items = list(items)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item
