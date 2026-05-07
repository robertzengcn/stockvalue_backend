"""SQLAlchemy base and database configuration."""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


# Base class for all ORM models
class Base(DeclarativeBase):
    """Base class for all ORM models."""


DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise RuntimeError(
        "DATABASE_URL environment variable is required. "
        "Set it to your PostgreSQL connection string, e.g. "
        "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    )

# Async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

# Async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database sessions.

    Yields:
        Async database session
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
