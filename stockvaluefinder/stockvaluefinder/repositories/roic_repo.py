"""Repository for ROIC analysis results data access."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.roic import ROICResultDB
from stockvaluefinder.repositories.base import BaseRepository

# ROICResultCreate and ROICResultUpdate are defined in Plan 01
# (stockvaluefinder/models/roic.py). During parallel execution they may
# not be available yet, so we use a lazy import with fallback to Any.
try:
    from stockvaluefinder.models.roic import ROICResultCreate, ROICResultUpdate
except ImportError:
    ROICResultCreate = Any  # type: ignore[assignment,misc]
    ROICResultUpdate = Any  # type: ignore[assignment,misc]


class ROICResultRepository(
    BaseRepository[ROICResultDB, ROICResultCreate, ROICResultUpdate]
):
    """Repository for ROIC-WACC spread analysis results.

    Provides domain-specific query methods for ROIC analysis results,
    including upsert by (ticker, fiscal_year) and multi-year retrieval
    for trend calculations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with ROICResultDB model.

        Args:
            session: Async database session
        """
        super().__init__(ROICResultDB, session)

    async def upsert_by_ticker_year(
        self,
        data: ROICResultCreate,
    ) -> ROICResultDB:
        """Insert or update ROIC result by ticker + fiscal_year.

        If a record already exists for the given ticker and fiscal_year,
        it is updated in place (preserving the original analysis_id).
        Otherwise, a new record is created.

        Pattern mirrors :meth:`RiskScoreRepository.upsert_by_report_id`.

        Args:
            data: ROICResultCreate Pydantic model with analysis data

        Returns:
            Created or updated ROICResultDB instance
        """
        stmt = select(ROICResultDB).where(
            ROICResultDB.ticker == data.ticker,
            ROICResultDB.fiscal_year == data.fiscal_year,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        field_values = dict(
            ticker=data.ticker,
            fiscal_year=data.fiscal_year,
            calculated_at=datetime.now(tz=timezone.utc),
            roic=data.roic,
            negative_invested_capital=data.negative_invested_capital,
            nopat=data.nopat,
            invested_capital=data.invested_capital,
            wacc=data.wacc,
            wacc_breakdown=data.wacc_breakdown,
            spread=data.spread,
            spread_classification=data.spread_classification,
            moat_trend=data.moat_trend,
            is_financial_sector=data.is_financial_sector,
            audit_trail=data.audit_trail,
        )

        if existing is not None:
            for field, value in field_values.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        db_obj = ROICResultDB(
            analysis_id=data.analysis_id,
            **field_values,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> list[ROICResultDB]:
        """Get ROIC analyses for ticker, most recent first.

        Args:
            ticker: Stock code (e.g. ``600519.SH``)
            limit: Maximum number of records to return

        Returns:
            List of ROICResultDB ordered by calculated_at descending
        """
        stmt = (
            select(ROICResultDB)
            .where(ROICResultDB.ticker == ticker)
            .order_by(ROICResultDB.fiscal_year.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_ticker(
        self,
        ticker: str,
    ) -> ROICResultDB | None:
        """Get the most recent ROIC analysis for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest ROICResultDB if found, None otherwise
        """
        stmt = (
            select(ROICResultDB)
            .where(ROICResultDB.ticker == ticker)
            .order_by(ROICResultDB.fiscal_year.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_year_for_ticker(
        self,
        ticker: str,
        years: int = 3,
    ) -> list[ROICResultDB]:
        """Get last N years of ROIC analyses for trend calculation.

        Args:
            ticker: Stock code
            years: Number of most recent years to retrieve

        Returns:
            List of ROICResultDB ordered by fiscal_year descending
        """
        stmt = (
            select(ROICResultDB)
            .where(ROICResultDB.ticker == ticker)
            .order_by(ROICResultDB.fiscal_year.desc())
            .limit(years)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
