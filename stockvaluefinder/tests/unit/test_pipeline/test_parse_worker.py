"""Unit tests for parse_report worker function.

Tests cover:
- Successful parse: task transitions PARSING->ANALYZING, DocumentService.process_upload called
- Document not found: task transitions to FAILED when no document record exists
- File not found: task transitions to FAILED when PDF file does not exist
- DocumentService error: task transitions to FAILED when process_upload raises exception
- Enqueue analyze: after successful parse, enqueues analyze_report job via arq
- Separate sessions: DocumentService uses its own session, pipeline uses its own session
"""

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
    state: str = "parsing",
) -> MagicMock:
    """Create a mock PipelineTaskDB object."""
    task = MagicMock()
    task.task_id = task_id or str(uuid4())
    task.ticker = ticker
    task.business_key = business_key
    task.state = state
    return task


def _make_document_db(
    task_id: str | None = None,
    file_path: str | None = "/tmp/uploads/600519.SH/2023/annual/test.pdf",
    document_id: str | None = None,
) -> MagicMock:
    """Create a mock PipelineDocumentDB object."""
    doc = MagicMock()
    doc.task_id = task_id or str(uuid4())
    doc.file_path = file_path
    doc.document_id = document_id or str(uuid4())
    return doc


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
) -> dict:
    """Build a worker context dict."""
    _, factory = _make_mock_session_ctx()
    return {
        "session_factory": session_factory or factory,
    }


# ---------------------------------------------------------------------------
# parse_report tests
# ---------------------------------------------------------------------------


class TestParseReport:
    """Tests for the parse_report worker function."""

    @pytest.mark.asyncio
    async def test_successful_parse_transitions_to_analyzing(self) -> None:
        """Successful parse transitions PARSING->ANALYZING."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)
        document = _make_document_db(task_id=task_id)
        pdf_bytes = b"%PDF-1.4 fake content"

        mock_session, mock_session_factory = _make_mock_session_ctx()

        # Mock task repo
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        # Mock doc repo
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

        # Mock DocumentService
        mock_upload_response = MagicMock()
        mock_upload_response.document_id = str(document.document_id)
        mock_upload_response.status = "completed"
        mock_upload_response.chunk_count = 42
        mock_upload_response.page_count = 10

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
            patch("stockvaluefinder.pipeline.worker.DocumentService") as MockDocService,
            patch(
                "stockvaluefinder.pipeline.worker.Path.read_bytes",
                return_value=pdf_bytes,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=True,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_analyze",
                new_callable=AsyncMock,
            ),
        ):
            # Configure DocumentService mock
            mock_ds_instance = AsyncMock()
            mock_ds_instance.process_upload = AsyncMock(
                return_value=mock_upload_response
            )
            MockDocService.return_value = mock_ds_instance

            await parse_report(ctx, task_id)

        # Verify transition to ANALYZING
        mock_task_repo.transition_state.assert_awaited()
        last_call = mock_task_repo.transition_state.call_args
        assert last_call[0][1] == PipelineState.ANALYZING
        assert last_call[1].get("current_stage") == "analyzing"

    @pytest.mark.asyncio
    async def test_process_upload_called_with_correct_args(self) -> None:
        """DocumentService.process_upload called with correct arguments."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id, ticker="600519.SH")
        document = _make_document_db(
            task_id=task_id,
            file_path="/tmp/uploads/600519.SH/2023/annual/test.pdf",
            document_id="doc-uuid-123",
        )
        pdf_bytes = b"%PDF-1.4 fake content"

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

        mock_upload_response = MagicMock()

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
            patch("stockvaluefinder.pipeline.worker.DocumentService") as MockDocService,
            patch(
                "stockvaluefinder.pipeline.worker.Path.read_bytes",
                return_value=pdf_bytes,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=True,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_analyze",
                new_callable=AsyncMock,
            ),
        ):
            mock_ds_instance = AsyncMock()
            mock_ds_instance.process_upload = AsyncMock(
                return_value=mock_upload_response
            )
            MockDocService.return_value = mock_ds_instance

            await parse_report(ctx, task_id)

        # Verify process_upload called with correct args
        mock_ds_instance.process_upload.assert_awaited_once()
        call_kwargs = mock_ds_instance.process_upload.call_args[1]
        assert call_kwargs["document_id"] == "doc-uuid-123"
        assert call_kwargs["ticker"] == "600519.SH"
        assert call_kwargs["file_name"] == "test.pdf"
        assert call_kwargs["file_path"] == "/tmp/uploads/600519.SH/2023/annual/test.pdf"
        assert call_kwargs["pdf_bytes"] == pdf_bytes

    @pytest.mark.asyncio
    async def test_document_not_found_transitions_to_failed(self) -> None:
        """Task transitions to FAILED when no document record exists."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        # Document not found
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=None)

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
        ):
            await parse_report(ctx, task_id)

        # Verify FAILED transition
        mock_task_repo.transition_state.assert_awaited()
        call_args = mock_task_repo.transition_state.call_args
        assert call_args[0][1] == PipelineState.FAILED
        assert "No document record" in call_args[1]["error_message"]

    @pytest.mark.asyncio
    async def test_file_not_found_transitions_to_failed(self) -> None:
        """Task transitions to FAILED when PDF file does not exist."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)
        # Document with file_path but file doesn't exist
        document = _make_document_db(
            task_id=task_id,
            file_path="/nonexistent/path/test.pdf",
        )

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

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
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=False,
            ),
        ):
            await parse_report(ctx, task_id)

        # Verify FAILED transition
        mock_task_repo.transition_state.assert_awaited()
        call_args = mock_task_repo.transition_state.call_args
        assert call_args[0][1] == PipelineState.FAILED
        assert "PDF file not found" in call_args[1]["error_message"]

    @pytest.mark.asyncio
    async def test_document_service_error_transitions_to_failed(self) -> None:
        """Task transitions to FAILED when process_upload raises exception."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)
        document = _make_document_db(task_id=task_id)
        pdf_bytes = b"%PDF-1.4 fake content"

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

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
            patch("stockvaluefinder.pipeline.worker.DocumentService") as MockDocService,
            patch(
                "stockvaluefinder.pipeline.worker.Path.read_bytes",
                return_value=pdf_bytes,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=True,
            ),
            pytest.raises(Exception, match="Embedding service unavailable"),
        ):
            # DocumentService.process_upload raises
            mock_ds_instance = AsyncMock()
            mock_ds_instance.process_upload = AsyncMock(
                side_effect=Exception("Embedding service unavailable")
            )
            MockDocService.return_value = mock_ds_instance

            await parse_report(ctx, task_id)

        # Verify FAILED transition
        failed_calls = [
            c
            for c in mock_task_repo.transition_state.call_args_list
            if c[0][1] == PipelineState.FAILED
        ]
        assert len(failed_calls) == 1
        assert "Embedding service unavailable" in failed_calls[0][1]["error_message"]

    @pytest.mark.asyncio
    async def test_enqueue_analyze_after_successful_parse(self) -> None:
        """analyze_report job enqueued after successful parse."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(
            task_id=task_id,
            business_key="600519.SH:2023:annual",
        )
        document = _make_document_db(task_id=task_id)
        pdf_bytes = b"%PDF-1.4 fake content"

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

        mock_upload_response = MagicMock()

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
            patch("stockvaluefinder.pipeline.worker.DocumentService") as MockDocService,
            patch(
                "stockvaluefinder.pipeline.worker.Path.read_bytes",
                return_value=pdf_bytes,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=True,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_analyze",
                new_callable=AsyncMock,
            ) as mock_enqueue,
        ):
            mock_ds_instance = AsyncMock()
            mock_ds_instance.process_upload = AsyncMock(
                return_value=mock_upload_response
            )
            MockDocService.return_value = mock_ds_instance

            await parse_report(ctx, task_id)

        mock_enqueue.assert_awaited_once_with(task_id, "600519.SH:2023:annual")

    @pytest.mark.asyncio
    async def test_uses_separate_sessions_for_document_service(self) -> None:
        """DocumentService gets a separate session from the pipeline session."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)
        document = _make_document_db(task_id=task_id)
        pdf_bytes = b"%PDF-1.4"

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

        mock_upload_response = MagicMock()

        mock_session_factory_copy = MagicMock()

        call_count = 0

        def _session_ctx_enter():
            nonlocal call_count
            call_count += 1
            return mock_session

        mock_session_factory_copy.return_value.__aenter__ = AsyncMock(
            side_effect=_session_ctx_enter
        )
        mock_session_factory_copy.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = _build_ctx(session_factory=mock_session_factory_copy)

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_task_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineDocumentRepository",
                return_value=mock_doc_repo,
            ),
            patch("stockvaluefinder.pipeline.worker.DocumentService") as MockDocService,
            patch(
                "stockvaluefinder.pipeline.worker.Path.read_bytes",
                return_value=pdf_bytes,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.Path.exists",
                return_value=True,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._enqueue_analyze",
                new_callable=AsyncMock,
            ),
        ):
            mock_ds_instance = AsyncMock()
            mock_ds_instance.process_upload = AsyncMock(
                return_value=mock_upload_response
            )
            MockDocService.return_value = mock_ds_instance

            await parse_report(ctx, task_id)

        # Session factory should be called twice (pipeline session + doc service session)
        assert mock_session_factory_copy.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_early_when_task_not_found(self) -> None:
        """parse_report returns early when task_id not found in DB."""
        from stockvaluefinder.pipeline.worker import parse_report

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=None)
        mock_task_repo.transition_state = AsyncMock()

        ctx = _build_ctx(session_factory=mock_session_factory)

        with patch(
            "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
            return_value=mock_task_repo,
        ):
            await parse_report(ctx, "nonexistent-task-id")

        # No state transition should have been attempted
        mock_task_repo.transition_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_file_path_transitions_to_failed(self) -> None:
        """Task transitions to FAILED when document has no file_path."""
        from stockvaluefinder.pipeline.worker import parse_report

        task_id = str(uuid4())
        task = _make_task_db(task_id=task_id)
        # Document with no file_path
        document = _make_document_db(task_id=task_id, file_path=None)

        mock_session, mock_session_factory = _make_mock_session_ctx()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task)
        mock_task_repo.transition_state = AsyncMock(return_value=task)

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_task_id = AsyncMock(return_value=document)

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
        ):
            await parse_report(ctx, task_id)

        # Verify FAILED transition
        mock_task_repo.transition_state.assert_awaited()
        call_args = mock_task_repo.transition_state.call_args
        assert call_args[0][1] == PipelineState.FAILED
        assert "PDF file not found" in call_args[1]["error_message"]
