"""Repository for Alpha composite score data access."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.alpha import AlphaScoreDB
from stockvaluefinder.repositories.base import BaseRepository

from stockvaluefinder.models.alpha import AlphaScoreCreate, AlphaScoreUpdate


class AlphaScoreRepository(
    BaseRepository[AlphaScoreDB, AlphaScoreCreate, AlphaScoreUpdate]
):
    """Repository for Alpha composite score analysis results.

    Provides domain-specific query methods for Alpha scores,
    including upsert by (ticker, fiscal_year) and retrieval
    for historical queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with AlphaScoreDB model.

        Args:
            session: Async database session
        """
        super().__init__(AlphaScoreDB, session)

    async def upsert_by_ticker_year(
        self,
        data: AlphaScoreCreate,
    ) -> AlphaScoreDB:
        """Insert or update Alpha score by ticker + fiscal_year.

        If a record already exists for the given ticker and fiscal_year,
        it is updated in place (preserving the original analysis_id).
        Otherwise, a new record is created.

        Pattern mirrors :meth:`ROICResultRepository.upsert_by_ticker_year`.

        Args:
            data: AlphaScoreCreate Pydantic model with analysis data

        Returns:
            Created or updated AlphaScoreDB instance
        """
        stmt = select(AlphaScoreDB).where(
            AlphaScoreDB.ticker == data.ticker,
            AlphaScoreDB.fiscal_year == data.fiscal_year,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        field_values = dict(
            ticker=data.ticker,
            fiscal_year=data.fiscal_year,
            calculated_at=datetime.now(tz=timezone.utc),
            roic_wacc_score=data.roic_wacc_score,
            roic_wacc_raw=data.roic_wacc_raw,
            capex_score=data.capex_score,
            capex_raw_grade=data.capex_raw_grade,
            policy_score=data.policy_score,
            policy_raw_score=data.policy_raw_score,
            moat_score=data.moat_score,
            moat_raw_trend=data.moat_raw_trend,
            alpha_score=data.alpha_score,
            weights_used=data.weights_used,
            dcf_adjustment_summary=data.dcf_adjustment_summary,
            audit_trail=data.audit_trail,
        )

        if existing is not None:
            for field, value in field_values.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        db_obj = AlphaScoreDB(
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
    ) -> AlphaScoreDB | None:
        """Get the most recent Alpha analysis for a ticker.

        Args:
            ticker: Stock code (e.g. ``600519.SH``)

        Returns:
            Latest AlphaScoreDB if found, None otherwise
        """
        stmt = (
            select(AlphaScoreDB)
            .where(AlphaScoreDB.ticker == ticker)
            .order_by(AlphaScoreDB.fiscal_year.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> list[AlphaScoreDB]:
        """Get Alpha analyses for ticker, most recent first.

        Args:
            ticker: Stock code (e.g. ``600519.SH``)
            limit: Maximum number of records to return

        Returns:
            List of AlphaScoreDB ordered by fiscal_year descending
        """
        stmt = (
            select(AlphaScoreDB)
            .where(AlphaScoreDB.ticker == ticker)
            .order_by(AlphaScoreDB.fiscal_year.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
