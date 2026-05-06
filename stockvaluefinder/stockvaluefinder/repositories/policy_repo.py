"""Repository for policy document data access.

Provides CRUD operations for PolicyDocumentDB records,
supporting the Policy Resonance Engine's document management.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.policy import PolicyDocumentDB
from stockvaluefinder.repositories.base import BaseRepository

# Lazy import with fallback to Any for parallel execution safety.
try:
    from stockvaluefinder.models.policy import (
        PolicyDocumentCreate,
        PolicyDocumentUpdate,
    )
except ImportError:
    PolicyDocumentCreate = Any  # type: ignore[assignment,misc]
    PolicyDocumentUpdate = Any  # type: ignore[assignment,misc]


class PolicyDocumentRepository(
    BaseRepository[PolicyDocumentDB, PolicyDocumentCreate, PolicyDocumentUpdate]
):
    """Repository for policy document records.

    Provides domain-specific query methods for policy documents,
    including lookup by document_id, filtering by policy_type,
    and deletion by document_id.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with PolicyDocumentDB model.

        Args:
            session: Async database session
        """
        super().__init__(PolicyDocumentDB, session)

    async def get_by_document_id(
        self,
        document_id: str,
    ) -> PolicyDocumentDB | None:
        """Get a policy document by its UUID.

        Args:
            document_id: UUID string of the document

        Returns:
            PolicyDocumentDB instance if found, None otherwise
        """
        stmt = select(PolicyDocumentDB).where(
            PolicyDocumentDB.document_id == document_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_policies(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PolicyDocumentDB]:
        """Get all policy documents with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of PolicyDocumentDB instances
        """
        stmt = (
            select(PolicyDocumentDB)
            .order_by(PolicyDocumentDB.upload_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_policy_type(
        self,
        policy_type: str,
    ) -> list[PolicyDocumentDB]:
        """Get all policy documents of a specific type.

        Args:
            policy_type: Type of policy to filter by
                (industry/fiscal/monetary/trade)

        Returns:
            List of matching PolicyDocumentDB instances
        """
        stmt = (
            select(PolicyDocumentDB)
            .where(PolicyDocumentDB.policy_type == policy_type)
            .order_by(PolicyDocumentDB.upload_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document_id(
        self,
        document_id: str,
    ) -> bool:
        """Delete a policy document by its UUID.

        Args:
            document_id: UUID string of the document to delete

        Returns:
            True if deleted, False if not found
        """
        doc = await self.get_by_document_id(document_id)
        if doc is None:
            return False

        await self._session.delete(doc)
        return True
