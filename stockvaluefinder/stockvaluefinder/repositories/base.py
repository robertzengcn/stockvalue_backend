"""Base repository class with common CRUD operations."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository with async CRUD operations.

    All repositories should inherit from this class and implement
    domain-specific query methods.
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            model: SQLAlchemy ORM model class
            session: Async database session
        """
        self.model = model
        self.session = session
        self._session = session  # Alias for backwards compatibility

    async def get_by_id(
        self,
        id: Any,  # noqa: A002
    ) -> ModelType | None:
        """Get entity by ID.

        Args:
            id: Entity primary key

        Returns:
            Entity instance or None if not found
        """
        stmt = select(self.model).where(self.model.id == id)  # type: ignore
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """Get all entities with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entity instances
        """
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: CreateSchemaType) -> ModelType:
        """Create new entity.

        Args:
            data: Pydantic schema with entity data

        Returns:
            Created entity instance
        """
        entity = self.model(**data.model_dump())
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(
        self,
        id: Any,  # noqa: A002
        data: UpdateSchemaType,
    ) -> ModelType | None:
        """Update entity.

        Args:
            id: Entity primary key
            data: Pydantic schema with update data

        Returns:
            Updated entity instance or None if not found
        """
        entity = await self.get_by_id(id)
        if entity is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)

        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: Any) -> bool:  # noqa: A002
        """Delete entity.

        Args:
            id: Entity primary key

        Returns:
            True if deleted, False if not found
        """
        entity = await self.get_by_id(id)
        if entity is None:
            return False

        await self.session.delete(entity)
        return True
