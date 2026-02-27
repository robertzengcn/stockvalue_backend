"""Shared pytest fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# TODO: Create test database fixtures
# - async database session
# - mock external API clients
# - test data factories
# - cache client mock


@pytest.fixture
async def db_session() -> AsyncSession:
    """Fixture for test database session."""
    # TODO: Implement test session
    raise NotImplementedError("Test fixture not yet implemented")
