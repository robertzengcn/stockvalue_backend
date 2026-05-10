"""Repository for User data access."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.user import UserDB


class UserRepository:
    """Repository for User data access with auth-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session
        """
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserDB | None:
        """Get user by primary key.

        Args:
            user_id: User UUID

        Returns:
            UserDB if found, None otherwise
        """
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserDB | None:
        """Get user by email address.

        Args:
            email: User email address

        Returns:
            UserDB if found, None otherwise
        """
        stmt = select(UserDB).where(UserDB.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: UserDB) -> UserDB:
        """Create a new user record.

        Args:
            user: UserDB instance with populated fields

        Returns:
            Created UserDB instance (refreshed from DB)
        """
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def count_users(self) -> int:
        """Count total number of users.

        Returns:
            Total user count
        """
        stmt = select(func.count()).select_from(UserDB)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def update_role(self, user_id: UUID, role: str) -> UserDB | None:
        """Update user role.

        Args:
            user_id: User UUID
            role: New role value ("admin" or "user")

        Returns:
            Updated UserDB if found, None otherwise
        """
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.role = role
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_active(self, user_id: UUID, is_active: bool) -> UserDB | None:
        """Set user active status.

        Args:
            user_id: User UUID
            is_active: New active status

        Returns:
            Updated UserDB if found, None otherwise
        """
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.is_active = is_active
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def list_users(
        self, page: int = 1, limit: int = 20
    ) -> tuple[list[UserDB], int]:
        """List users with pagination, excluding soft-deleted users.

        Args:
            page: Page number (1-based), clamped to minimum 1
            limit: Items per page, clamped to range [1, 100]

        Returns:
            Tuple of (list of UserDB for current page, total count of active users)
        """
        page = max(1, page)
        limit = max(1, min(100, limit))
        offset_val = (page - 1) * limit

        count_stmt = (
            select(func.count()).select_from(UserDB).where(UserDB.deleted_at.is_(None))
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        list_stmt = (
            select(UserDB)
            .where(UserDB.deleted_at.is_(None))
            .order_by(UserDB.created_at.desc())
            .offset(offset_val)
            .limit(limit)
        )
        list_result = await self._session.execute(list_stmt)
        users = list(list_result.scalars().all())

        return users, total

    async def soft_delete(self, user_id: UUID) -> UserDB | None:
        """Soft delete a user by setting deleted_at timestamp.

        Args:
            user_id: User UUID

        Returns:
            Updated UserDB if found and not already deleted, None otherwise
        """
        stmt = select(UserDB).where(UserDB.id == user_id, UserDB.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.deleted_at = datetime.utcnow()
        await self._session.flush()
        await self._session.refresh(user)
        return user
