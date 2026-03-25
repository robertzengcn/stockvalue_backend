"""Repository for RiskScore data access."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.risk import RiskScoreDB
from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import RiskScoreCreate, RiskScoreUpdate
from stockvaluefinder.repositories.base import BaseRepository


class RiskScoreRepository(
    BaseRepository[RiskScoreDB, RiskScoreCreate, RiskScoreUpdate]
):
    """Repository for RiskScore data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with RiskScoreDB model."""
        super().__init__(RiskScoreDB, session)

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[RiskScoreDB]:
        """Get all risk scores for a given ticker.

        Args:
            ticker: Stock code (e.g., '600519.SH')
            limit: Maximum number of records to return

        Returns:
            List of RiskScoreDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.ticker == ticker,
            )
            .order_by(
                RiskScoreDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_score_id(
        self,
        score_id: UUID,
    ) -> RiskScoreDB | None:
        """Get risk score by primary key.

        Args:
            score_id: Primary key UUID

        Returns:
            RiskScoreDB if found, None otherwise
        """
        stmt = select(RiskScoreDB).where(
            RiskScoreDB.score_id == score_id,
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_report_id(
        self,
        report_id: UUID,
    ) -> RiskScoreDB | None:
        """Get risk score by financial report ID.

        Args:
            report_id: Foreign key to financial_reports

        Returns:
            RiskScoreDB if found, None otherwise
        """
        stmt = select(RiskScoreDB).where(
            RiskScoreDB.report_id == report_id,
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_ticker(
        self,
        ticker: str,
    ) -> RiskScoreDB | None:
        """Get the latest risk score for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest RiskScoreDB if found, None otherwise
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.ticker == ticker,
            )
            .order_by(
                RiskScoreDB.calculated_at.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_risk_level(
        self,
        risk_level: RiskLevel,
        limit: int = 100,
    ) -> list[RiskScoreDB]:
        """Get all risk scores with a specific risk level.

        Args:
            risk_level: Risk level enum (LOW, MEDIUM, HIGH, CRITICAL)
            limit: Maximum number of records to return

        Returns:
            List of RiskScoreDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.risk_level == risk_level.value,
            )
            .order_by(
                RiskScoreDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_high_risk_stocks(
        self,
        min_m_score: float = -1.78,
        limit: int = 100,
    ) -> list[RiskScoreDB]:
        """Get stocks with high M-Score indicating potential manipulation.

        Args:
            min_m_score: Minimum M-Score threshold (default -1.78)
            limit: Maximum number of records to return

        Returns:
            List of RiskScoreDB with M-Score >= threshold, ordered by m_score (highest first)
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.m_score >= min_m_score,
            )
            .order_by(
                RiskScoreDB.m_score.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_存贷双高_stocks(
        self,
        limit: int = 100,
    ) -> list[RiskScoreDB]:
        """Get stocks flagged with 存贷双高 anomaly.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of RiskScoreDB with 存贷双高 flag, ordered by calculated_at (most recent first)
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.存贷双高.is_(True),
            )
            .order_by(
                RiskScoreDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> list[RiskScoreDB]:
        """Get risk scores calculated within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum number of records to return

        Returns:
            List of RiskScoreDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(RiskScoreDB)
            .where(
                RiskScoreDB.calculated_at >= start_date,
                RiskScoreDB.calculated_at <= end_date,
            )
            .order_by(
                RiskScoreDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        data: RiskScoreCreate,
    ) -> RiskScoreDB:
        """Create a new risk score record.

        Args:
            data: RiskScoreCreate Pydantic model

        Returns:
            Created RiskScoreDB instance
        """
        from decimal import Decimal

        db_obj = RiskScoreDB(
            score_id=data.score_id,
            ticker=data.ticker,
            report_id=data.report_id,
            risk_level=data.risk_level.value,
            calculated_at=data.calculated_at,
            # Beneish M-Score
            m_score=data.m_score,
            mscore_data=data.mscore_data.model_dump(),
            # 存贷双高
            存贷双高=data.存贷双高,
            cash_amount=Decimal(str(data.cash_amount)),
            debt_amount=Decimal(str(data.debt_amount)),
            cash_growth_rate=data.cash_growth_rate,
            debt_growth_rate=data.debt_growth_rate,
            # Goodwill risk
            goodwill_ratio=data.goodwill_ratio,
            goodwill_excessive=data.goodwill_excessive,
            # Cash flow divergence
            profit_cash_divergence=data.profit_cash_divergence,
            profit_growth=data.profit_growth,
            ocf_growth=data.ocf_growth,
            # Red flags
            red_flags=data.red_flags,
        )

        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        score_id: UUID,
        data: RiskScoreUpdate,
    ) -> RiskScoreDB | None:
        """Update an existing risk score.

        Args:
            score_id: Primary key UUID
            data: RiskScoreUpdate Pydantic model

        Returns:
            Updated RiskScoreDB if found, None otherwise
        """
        from decimal import Decimal

        stmt = select(RiskScoreDB).where(
            RiskScoreDB.score_id == score_id,
        )
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj is None:
            return None

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in ("cash_amount", "debt_amount"):
                # Convert Decimal fields
                setattr(db_obj, field, Decimal(str(value)))
            elif field == "risk_level" and isinstance(value, RiskLevel):
                # Convert enum to string
                setattr(db_obj, field, value.value)
            elif field == "mscore_data":
                # Ensure dict type for JSONB
                setattr(db_obj, field, dict(value))
            else:
                setattr(db_obj, field, value)

        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def delete_by_report_id(
        self,
        report_id: UUID,
    ) -> bool:
        """Delete risk score by report ID.

        Args:
            report_id: Foreign key to financial_reports

        Returns:
            True if deleted, False if not found
        """
        stmt = select(RiskScoreDB).where(
            RiskScoreDB.report_id == report_id,
        )
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj is None:
            return False

        await self._session.delete(db_obj)
        await self._session.flush()
        return True
