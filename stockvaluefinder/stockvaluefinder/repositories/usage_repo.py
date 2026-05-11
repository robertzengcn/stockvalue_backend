"""Repository for API usage record data access.

Provides upsert and aggregation queries for the api_usage_records table,
which stores flushed usage counters from Redis.
"""

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.api_usage_record import ApiUsageRecordDB

logger = logging.getLogger(__name__)


class ApiUsageRepository:
    """Repository for API usage record CRUD and aggregation queries.

    Args:
        session: Async database session
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_usage(
        self,
        user_id: str,
        endpoint: str,
        call_count: int,
        error_count: int,
        period_start: datetime,
        period_end: datetime,
    ) -> ApiUsageRecordDB:
        """Upsert usage record for a user+endpoint+period combination.

        If a record already exists for the same user_id, endpoint, and
        period_start, it increments the existing counts. Otherwise, a new
        record is created.

        Args:
            user_id: User identifier
            endpoint: API endpoint path
            call_count: Number of new calls to add
            error_count: Number of new errors to add
            period_start: Start of the aggregation period
            period_end: End of the aggregation period

        Returns:
            The created or updated ApiUsageRecordDB instance
        """
        stmt = select(ApiUsageRecordDB).where(
            ApiUsageRecordDB.user_id == user_id,
            ApiUsageRecordDB.endpoint == endpoint,
            ApiUsageRecordDB.period_start == period_start,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.call_count += call_count
            existing.error_count += error_count
            await self._session.flush()
            return existing

        record = ApiUsageRecordDB(
            user_id=user_id,
            endpoint=endpoint,
            call_count=call_count,
            error_count=error_count,
            period_start=period_start,
            period_end=period_end,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_user_totals(self, user_id: str) -> dict[str, int]:
        """Get total calls and errors for a user across all periods.

        Args:
            user_id: User identifier

        Returns:
            Dict with total_calls and total_errors keys
        """
        stmt = select(
            func.coalesce(func.sum(ApiUsageRecordDB.call_count), 0).label(
                "total_calls"
            ),
            func.coalesce(func.sum(ApiUsageRecordDB.error_count), 0).label(
                "total_errors"
            ),
        ).where(ApiUsageRecordDB.user_id == user_id)

        result = await self._session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return {"total_calls": 0, "total_errors": 0}

        return {"total_calls": row.total_calls, "total_errors": row.total_errors}

    async def get_aggregate_stats(self, limit: int = 10) -> dict:
        """Get aggregate usage statistics across all users.

        Returns total calls, total errors, and top users ranked by
        total call count.

        Args:
            limit: Maximum number of top users to return

        Returns:
            Dict with total_calls, total_errors, error_rate, and top_users list
        """
        # Total calls and errors
        totals_stmt = select(
            func.coalesce(func.sum(ApiUsageRecordDB.call_count), 0).label(
                "total_calls"
            ),
            func.coalesce(func.sum(ApiUsageRecordDB.error_count), 0).label(
                "total_errors"
            ),
        )
        totals_result = await self._session.execute(totals_stmt)
        totals_row = totals_result.one()

        # Top users by usage
        top_users_stmt = (
            select(
                ApiUsageRecordDB.user_id,
                func.sum(ApiUsageRecordDB.call_count).label("total_calls"),
            )
            .group_by(ApiUsageRecordDB.user_id)
            .order_by(func.sum(ApiUsageRecordDB.call_count).desc())
            .limit(limit)
        )
        top_users_result = await self._session.execute(top_users_stmt)
        top_users_rows = top_users_result.all()

        total_calls = totals_row.total_calls
        total_errors = totals_row.total_errors
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0

        return {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": error_rate,
            "top_users": [
                {"user_id": row.user_id, "total_calls": row.total_calls}
                for row in top_users_rows
            ],
        }
