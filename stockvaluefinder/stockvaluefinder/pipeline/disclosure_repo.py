"""PendingDisclosureRepository for pending_disclosures staging table.

Provides database operations for the pending_disclosures staging table:
- Staging disclosures from a poll cycle (bulk insert)
- Reading unprocessed disclosures for a specific poll
- Marking disclosures as processed after handling
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.pending_disclosure import PendingDisclosureDB
from stockvaluefinder.pipeline.models import PendingDisclosureCreate

logger = logging.getLogger(__name__)


class PendingDisclosureRepository:
    """Repository for pending disclosure staging table operations.

    The pending_disclosures table acts as a staging area between the
    poll cron and the process job. The cron writes raw disclosure data
    here, and the process job reads from this table to detect new vs.
    amended reports and enqueue download jobs (D-11).

    Args:
        session: Async database session for all operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session for all operations.
        """
        self._session = session

    async def stage_disclosures(
        self,
        poll_id: UUID,
        disclosures: list[PendingDisclosureCreate],
    ) -> int:
        """Write multiple disclosure rows with the same poll_id.

        Bulk inserts all disclosures from a single poll cycle into
        the staging table for later processing.

        Args:
            poll_id: UUID linking disclosures from the same poll cycle.
            disclosures: List of PendingDisclosureCreate models to stage.

        Returns:
            Number of rows inserted.
        """
        if not disclosures:
            return 0

        for disc in disclosures:
            row = PendingDisclosureDB(
                disclosure_id=uuid4(),
                poll_id=poll_id,
                ticker=disc.ticker,
                stock_name=disc.stock_name,
                report_type=disc.report_type,
                fiscal_year=disc.fiscal_year,
                disclosure_date=disc.disclosure_date,
                first_appointment=disc.first_appointment,
                source=disc.source,
                source_raw=disc.source_raw,
                processed=False,
                created_at=datetime.now(timezone.utc),
                processed_at=None,
            )
            self._session.add(row)

        await self._session.flush()
        logger.info(
            "Staged disclosures",
            extra={"poll_id": str(poll_id), "count": len(disclosures)},
        )
        return len(disclosures)

    async def get_unprocessed(self, poll_id: UUID) -> list[PendingDisclosureDB]:
        """Get unprocessed rows for a specific poll cycle.

        Returns rows where processed=False and poll_id matches,
        ordered by created_at for deterministic processing.

        Args:
            poll_id: UUID of the poll cycle to query.

        Returns:
            List of unprocessed PendingDisclosureDB rows.
        """
        stmt = (
            select(PendingDisclosureDB)
            .where(
                PendingDisclosureDB.poll_id == poll_id,
                PendingDisclosureDB.processed.is_(False),
            )
            .order_by(PendingDisclosureDB.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_processed(self, disclosure_ids: list[str]) -> int:
        """Mark disclosures as processed.

        Sets processed=True and processed_at=current UTC time for
        the given disclosure IDs.

        Args:
            disclosure_ids: List of disclosure_id values to mark.

        Returns:
            Number of rows updated.
        """
        if not disclosure_ids:
            return 0

        now = datetime.now(timezone.utc)
        stmt = (
            update(PendingDisclosureDB)
            .where(PendingDisclosureDB.disclosure_id.in_(disclosure_ids))
            .values(processed=True, processed_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        count = result.rowcount  # type: ignore[attr-defined]
        logger.info(
            "Marked disclosures as processed",
            extra={"count": count},
        )
        return count


__all__ = ["PendingDisclosureRepository"]
