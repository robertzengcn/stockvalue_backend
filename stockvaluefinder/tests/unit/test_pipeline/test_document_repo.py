"""Unit tests for PipelineDocumentRepository."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.db.models.pipeline_document import PipelineDocumentDB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_document_db(
    document_id: str | None = None,
    task_id: str | None = None,
    source_url: str | None = None,
    source_id: str | None = None,
    content_hash: str | None = None,
    file_path: str | None = None,
    file_size: int | None = None,
    downloaded_at: datetime | None = None,
) -> MagicMock:
    """Create a mock PipelineDocumentDB object."""
    doc = MagicMock(spec=PipelineDocumentDB)
    doc.document_id = document_id or str(uuid.uuid4())
    doc.task_id = task_id or str(uuid.uuid4())
    doc.source_url = source_url
    doc.source_id = source_id
    doc.content_hash = content_hash
    doc.file_path = file_path
    doc.file_size = file_size
    doc.downloaded_at = downloaded_at or datetime.now(timezone.utc)
    return doc


def _mock_session(return_scalars: list | None = None) -> AsyncMock:
    """Create a mock AsyncSession.

    Args:
        return_scalars: List of values to return from sequential
            scalar_one_or_none calls.
    """
    session = AsyncMock()
    result_mock = MagicMock()

    if return_scalars is None:
        return_scalars = []

    scalar_idx = 0

    def _scalar_one_or_none():
        nonlocal scalar_idx
        if scalar_idx < len(return_scalars):
            val = return_scalars[scalar_idx]
            scalar_idx += 1
            return val
        return None

    result_mock.scalar_one_or_none = _scalar_one_or_none

    session.execute.return_value = result_mock
    return session


# ---------------------------------------------------------------------------
# create_document tests
# ---------------------------------------------------------------------------


class TestCreateDocument:
    """Tests for PipelineDocumentRepository.create_document."""

    @pytest.mark.asyncio
    async def test_create_document_with_all_fields(self) -> None:
        """create_document inserts a PipelineDocumentDB record with all fields."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineDocumentRepository(session)

        task_id = str(uuid.uuid4())
        await repo.create_document(
            task_id=task_id,
            source_url="https://static.cninfo.com.cn/12345.PDF",
            source_id="ann-12345",
            content_hash="abcdef1234567890" * 4,
            file_path="./uploads/600519.SH/2023/annual/ann-12345.pdf",
            file_size=1024000,
        )

        # Verify session.add was called with correct fields
        assert session.add.called
        added_obj = session.add.call_args[0][0]
        assert isinstance(added_obj, PipelineDocumentDB)
        assert added_obj.task_id == task_id
        assert added_obj.source_url == "https://static.cninfo.com.cn/12345.PDF"
        assert added_obj.source_id == "ann-12345"
        assert added_obj.content_hash == "abcdef1234567890" * 4
        assert added_obj.file_path == "./uploads/600519.SH/2023/annual/ann-12345.pdf"
        assert added_obj.file_size == 1024000
        assert added_obj.downloaded_at is not None

        # Verify flush and refresh were called
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_document_returns_flushed_record(self) -> None:
        """create_document returns the PipelineDocumentDB after flush+refresh."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineDocumentRepository(session)

        task_id = str(uuid.uuid4())
        result = await repo.create_document(task_id=task_id)

        # Result is the object that was added (refreshed)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_document_with_optional_fields_none(self) -> None:
        """create_document works with only required task_id field."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineDocumentRepository(session)

        task_id = str(uuid.uuid4())
        await repo.create_document(task_id=task_id)

        added_obj = session.add.call_args[0][0]
        assert isinstance(added_obj, PipelineDocumentDB)
        assert added_obj.source_url is None
        assert added_obj.source_id is None
        assert added_obj.content_hash is None
        assert added_obj.file_path is None
        assert added_obj.file_size is None


# ---------------------------------------------------------------------------
# get_by_content_hash tests
# ---------------------------------------------------------------------------


class TestGetByContentHash:
    """Tests for PipelineDocumentRepository.get_by_content_hash."""

    @pytest.mark.asyncio
    async def test_returns_matching_document(self) -> None:
        """get_by_content_hash returns document when hash exists."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        expected = _make_document_db(content_hash="abc123")
        session = _mock_session(return_scalars=[expected])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_content_hash("abc123")

        assert result is expected
        assert result.content_hash == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """get_by_content_hash returns None when no document matches."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_content_hash("nonexistent-hash")

        assert result is None


# ---------------------------------------------------------------------------
# get_by_source_id tests
# ---------------------------------------------------------------------------


class TestGetBySourceId:
    """Tests for PipelineDocumentRepository.get_by_source_id."""

    @pytest.mark.asyncio
    async def test_returns_matching_document(self) -> None:
        """get_by_source_id returns document when source_id exists."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        expected = _make_document_db(source_id="ann-99999")
        session = _mock_session(return_scalars=[expected])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_source_id("ann-99999")

        assert result is expected
        assert result.source_id == "ann-99999"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """get_by_source_id returns None when no document matches."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_source_id("nonexistent-id")

        assert result is None


# ---------------------------------------------------------------------------
# get_by_task_id tests
# ---------------------------------------------------------------------------


class TestGetByTaskId:
    """Tests for PipelineDocumentRepository.get_by_task_id."""

    @pytest.mark.asyncio
    async def test_returns_matching_document(self) -> None:
        """get_by_task_id returns document when task_id exists."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        task_id = str(uuid.uuid4())
        expected = _make_document_db(task_id=task_id)
        session = _mock_session(return_scalars=[expected])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_task_id(task_id)

        assert result is expected
        assert result.task_id == task_id

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        """get_by_task_id returns None when no document matches."""
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineDocumentRepository(session)

        result = await repo.get_by_task_id("nonexistent-task-id")

        assert result is None


# ---------------------------------------------------------------------------
# content_hash dedup tests
# ---------------------------------------------------------------------------


class TestContentHashDedup:
    """Tests for content_hash deduplication behavior."""

    @pytest.mark.asyncio
    async def test_duplicate_content_hash_does_not_raise(self) -> None:
        """Creating a second document with same content_hash does not raise.

        Content hash duplicates are tracked at application level, not
        enforced by a unique constraint. The repository allows inserting
        multiple records with the same hash; dedup logic is in the worker.
        """
        from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository

        session = _mock_session()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineDocumentRepository(session)

        hash_value = "a" * 64

        # Create two documents with same content_hash
        await repo.create_document(
            task_id=str(uuid.uuid4()),
            content_hash=hash_value,
        )
        await repo.create_document(
            task_id=str(uuid.uuid4()),
            content_hash=hash_value,
        )

        # Both should have been added without error
        assert session.add.call_count == 2
