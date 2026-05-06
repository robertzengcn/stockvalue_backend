"""Unit tests for PolicyDocumentRepository.

Tests CRUD operations for policy documents using a mocked AsyncSession,
following the established repository test patterns.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from stockvaluefinder.models.policy import (
    PolicyDocumentCreate,
)
from stockvaluefinder.repositories.policy_repo import PolicyDocumentRepository


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository tests."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


def _make_policy_doc(
    document_id: str | None = None,
    title: str = "Test Policy",
    policy_type: str = "industry",
    issuing_body: str = "国务院",
) -> SimpleNamespace:
    """Create a SimpleNamespace mimicking a PolicyDocumentDB for testing.

    Using SimpleNamespace avoids SQLAlchemy managed attribute issues
    when constructing objects without a proper session.
    """
    return SimpleNamespace(
        document_id=document_id or str(uuid4()),
        title=title,
        policy_type=policy_type,
        issuing_body=issuing_body,
        effective_date=None,
        industry_tags=["制造业"],
        file_path="/data/policies/test.pdf",
        page_count=10,
        chunk_count=25,
        upload_date=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
class TestPolicyDocumentRepository:
    """Test suite for PolicyDocumentRepository."""

    async def test_get_by_document_id_found(self):
        """Test retrieving a policy document by document_id."""
        session = _make_mock_session()
        doc = _make_policy_doc()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.get_by_document_id(doc.document_id)

        assert result is not None
        assert result.document_id == doc.document_id
        assert result.title == "Test Policy"

    async def test_get_by_document_id_not_found(self):
        """Test retrieving a non-existent document returns None."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.get_by_document_id(str(uuid4()))

        assert result is None

    async def test_get_all_policies(self):
        """Test retrieving all policies with pagination."""
        session = _make_mock_session()
        docs = [_make_policy_doc(title=f"Policy {i}") for i in range(3)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = docs
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.get_all_policies(limit=10, offset=0)

        assert len(result) == 3
        assert result[0].title == "Policy 0"

    async def test_get_all_policies_default_pagination(self):
        """Test default pagination parameters."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.get_all_policies()

        assert result == []

    async def test_get_by_policy_type(self):
        """Test retrieving policies filtered by type."""
        session = _make_mock_session()
        fiscal_docs = [_make_policy_doc(title="Tax Reform", policy_type="fiscal")]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = fiscal_docs
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.get_by_policy_type("fiscal")

        assert len(result) == 1
        assert result[0].policy_type == "fiscal"

    async def test_delete_by_document_id_found(self):
        """Test deleting an existing document."""
        session = _make_mock_session()
        doc = _make_policy_doc()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.delete_by_document_id(doc.document_id)

        assert result is True
        session.delete.assert_called_once_with(doc)

    async def test_delete_by_document_id_not_found(self):
        """Test deleting a non-existent document returns False."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = PolicyDocumentRepository(session)
        result = await repo.delete_by_document_id(str(uuid4()))

        assert result is False
        session.delete.assert_not_called()

    async def test_create_policy_document(self):
        """Test creating a new policy document."""
        session = _make_mock_session()
        doc_id = str(uuid4())

        create_data = PolicyDocumentCreate(
            document_id=doc_id,
            title="New Energy Policy",
            policy_type="industry",
            issuing_body="发改委",
            effective_date="2026-01-01",
            industry_tags=["新能源", "光伏"],
            file_path="/data/policies/new_energy.pdf",
            page_count=15,
            chunk_count=30,
        )

        def mock_refresh(entity):
            entity.title = create_data.title
            entity.policy_type = create_data.policy_type
            entity.issuing_body = create_data.issuing_body

        session.refresh = AsyncMock(side_effect=mock_refresh)

        repo = PolicyDocumentRepository(session)
        result = await repo.create(create_data)

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result.title == "New Energy Policy"
