"""Repository for FinancialReport data access."""

from datetime import date, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.financial import FinancialReportDB
from stockvaluefinder.models.enums import ReportType
from stockvaluefinder.models.financial import (
    FinancialReportCreate,
    FinancialReportUpdate,
)
from stockvaluefinder.repositories.base import BaseRepository


class FinancialReportRepository(
    BaseRepository[FinancialReportDB, FinancialReportCreate, FinancialReportUpdate]
):
    """Repository for FinancialReport data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with FinancialReportDB model."""
        super().__init__(FinancialReportDB, session)

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[FinancialReportDB]:
        """Get all financial reports for a given ticker.

        Args:
            ticker: Stock code (e.g., '600519.SH')
            limit: Maximum number of records to return

        Returns:
            List of FinancialReportDB objects ordered by period (most recent first)
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
            )
            .order_by(
                FinancialReportDB.period.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker_and_period(
        self,
        ticker: str,
        period: date,
    ) -> FinancialReportDB | None:
        """Get financial report by ticker and period.

        Args:
            ticker: Stock code
            period: Reporting period date

        Returns:
            FinancialReportDB if found, None otherwise
        """
        stmt = select(FinancialReportDB).where(
            FinancialReportDB.ticker == ticker,
            FinancialReportDB.period == period,
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ticker_and_fiscal_year(
        self,
        ticker: str,
        fiscal_year: int,
    ) -> list[FinancialReportDB]:
        """Get all financial reports for a ticker in a given fiscal year.

        Args:
            ticker: Stock code
            fiscal_year: Fiscal year (e.g., 2023)

        Returns:
            List of FinancialReportDB objects (annual + quarterly reports)
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
                FinancialReportDB.fiscal_year == fiscal_year,
            )
            .order_by(
                FinancialReportDB.period.desc(),
            )
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_annual(
        self,
        ticker: str,
    ) -> FinancialReportDB | None:
        """Get the latest annual report for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest annual FinancialReportDB if found, None otherwise
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
                FinancialReportDB.report_type == ReportType.ANNUAL,
            )
            .order_by(
                FinancialReportDB.fiscal_year.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_quarterly(
        self,
        ticker: str,
    ) -> FinancialReportDB | None:
        """Get the latest quarterly report for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest quarterly FinancialReportDB if found, None otherwise
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
                FinancialReportDB.report_type == ReportType.QUARTERLY,
            )
            .order_by(
                FinancialReportDB.period.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_previous_year_report(
        self,
        ticker: str,
        current_fiscal_year: int,
    ) -> FinancialReportDB | None:
        """Get the previous year's annual report for comparison.

        Args:
            ticker: Stock code
            current_fiscal_year: Current fiscal year

        Returns:
            Previous year's annual FinancialReportDB if found, None otherwise
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
                FinancialReportDB.report_type == ReportType.ANNUAL,
                FinancialReportDB.fiscal_year == current_fiscal_year - 1,
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        data: FinancialReportCreate,
    ) -> FinancialReportDB:
        """Create a new financial report record.

        Args:
            data: FinancialReportCreate Pydantic model

        Returns:
            Created FinancialReportDB instance
        """
        from datetime import datetime

        db_obj = FinancialReportDB(
            ticker=data.ticker,
            period=data.period,
            report_type=data.report_type,
            fiscal_year=data.fiscal_year,
            fiscal_quarter=data.fiscal_quarter,
            # Income statement
            revenue=data.revenue,
            net_income=data.net_income,
            operating_cash_flow=data.operating_cash_flow,
            gross_margin=data.gross_margin,
            # Balance sheet
            assets_total=data.assets_total,
            liabilities_total=data.liabilities_total,
            equity_total=data.equity_total,
            accounts_receivable=data.accounts_receivable,
            inventory=data.inventory,
            fixed_assets=data.fixed_assets,
            goodwill=data.goodwill,
            cash_and_equivalents=data.cash_and_equivalents,
            interest_bearing_debt=data.interest_bearing_debt,
            # Metadata
            report_source=data.report_source,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        report_id: UUID,
        data: FinancialReportUpdate,
    ) -> FinancialReportDB | None:
        """Update an existing financial report.

        Args:
            report_id: Primary key UUID
            data: FinancialReportUpdate Pydantic model

        Returns:
            Updated FinancialReportDB if found, None otherwise
        """
        from datetime import datetime

        stmt = select(FinancialReportDB).where(
            FinancialReportDB.report_id == report_id,
        )
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj is None:
            return None

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db_obj.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def exists_for_ticker_and_period(
        self,
        ticker: str,
        period: date,
    ) -> bool:
        """Check if a financial report exists for the given ticker and period.

        Args:
            ticker: Stock code
            period: Reporting period date

        Returns:
            True if exists, False otherwise
        """
        stmt = (
            select(FinancialReportDB)
            .where(
                FinancialReportDB.ticker == ticker,
                FinancialReportDB.period == period,
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
