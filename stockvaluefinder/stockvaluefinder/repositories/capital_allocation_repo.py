"""Repository for capital allocation scorecard results data access."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.capital_allocation import CapitalAllocationScoreDB
from stockvaluefinder.repositories.base import BaseRepository

# Lazy import with fallback to Any for parallel execution safety.
try:
    from stockvaluefinder.models.capital_allocation import (
        CapitalAllocationScoreCreate,
        CapitalAllocationScoreUpdate,
    )
except ImportError:
    CapitalAllocationScoreCreate = Any  # type: ignore[assignment,misc]
    CapitalAllocationScoreUpdate = Any  # type: ignore[assignment,misc]


class CapitalAllocationRepository(
    BaseRepository[
        CapitalAllocationScoreDB,
        CapitalAllocationScoreCreate,
        CapitalAllocationScoreUpdate,
    ]
):
    """Repository for capital allocation scorecard results.

    Provides domain-specific query methods for capital allocation scores,
    including upsert by (ticker, fiscal_year) and latest retrieval.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with CapitalAllocationScoreDB model.

        Args:
            session: Async database session
        """
        super().__init__(CapitalAllocationScoreDB, session)

    async def upsert_by_ticker_year(
        self,
        data: CapitalAllocationScoreCreate,
    ) -> CapitalAllocationScoreDB:
        """Insert or update capital allocation score by ticker + fiscal_year.

        If a record already exists for the given ticker and fiscal_year,
        it is updated in place (preserving the original analysis_id).
        Otherwise, a new record is created.

        Pattern mirrors :meth:`ROICResultRepository.upsert_by_ticker_year`.

        Args:
            data: CapitalAllocationScoreCreate Pydantic model with analysis data

        Returns:
            Created or updated CapitalAllocationScoreDB instance
        """
        stmt = select(CapitalAllocationScoreDB).where(
            CapitalAllocationScoreDB.ticker == data.ticker,
            CapitalAllocationScoreDB.fiscal_year == data.fiscal_year,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        field_values = dict(
            ticker=data.ticker,
            fiscal_year=data.fiscal_year,
            calculated_at=datetime.now(tz=timezone.utc),
            buyback_yield_data=data.buyback_yield_data,
            dividend_stability_data=data.dividend_stability_data,
            expansion_discipline_data=data.expansion_discipline_data,
            overall_grade=data.overall_grade,
            weighting=data.weighting,
            audit_trail=data.audit_trail,
        )

        if existing is not None:
            for field, value in field_values.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        db_obj = CapitalAllocationScoreDB(
            analysis_id=data.analysis_id,
            **field_values,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def get_latest_for_ticker(
        self,
        ticker: str,
    ) -> CapitalAllocationScoreDB | None:
        """Get the most recent capital allocation score for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest CapitalAllocationScoreDB if found, None otherwise
        """
        stmt = (
            select(CapitalAllocationScoreDB)
            .where(CapitalAllocationScoreDB.ticker == ticker)
            .order_by(CapitalAllocationScoreDB.fiscal_year.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
