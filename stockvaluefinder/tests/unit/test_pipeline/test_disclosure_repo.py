"""Unit tests for PendingDisclosureRepository."""

from datetime import date
from uuid import uuid4

from unittest.mock import AsyncMock, MagicMock

import pytest

from stockvaluefinder.db.models.pending_disclosure import PendingDisclosureDB
from stockvaluefinder.pipeline.models import PendingDisclosureCreate


# ---------------------------------------------------------------------------
# PendingDisclosureRepository.stage_disclosures
# ---------------------------------------------------------------------------


class TestStageDisclosures:
    """Tests for PendingDisclosureRepository.stage_disclosures."""

    @pytest.mark.asyncio
    async def test_stages_multiple_rows_with_same_poll_id(self) -> None:
        """stage_disclosures writes multiple rows with same poll_id."""
        from stockvaluefinder.pipeline.disclosure_repo import (
            PendingDisclosureRepository,
        )

        poll_id = uuid4()

        disclosures = [
            PendingDisclosureCreate(
                ticker="600519.SH",
                stock_name="Kweichow Moutai",
                report_type="annual",
                fiscal_year=2023,
                disclosure_date=date(2024, 4, 30),
                first_appointment=date(2024, 3, 15),
                source="akshare",
                source_raw={"raw_code": "600519"},
            ),
            PendingDisclosureCreate(
                ticker="000001.SZ",
                stock_name="Ping An Bank",
                report_type="annual",
                fiscal_year=2023,
                disclosure_date=date(2024, 4, 20),
                first_appointment=date(2024, 3, 10),
                source="akshare",
                source_raw={"raw_code": "000001"},
            ),
        ]

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        repo = PendingDisclosureRepository(mock_session)
        count = await repo.stage_disclosures(poll_id, disclosures)

        assert count == 2
        assert mock_session.add.call_count == 2
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stages_empty_list(self) -> None:
        """stage_disclosures returns 0 for empty list."""
        from stockvaluefinder.pipeline.disclosure_repo import (
            PendingDisclosureRepository,
        )

        poll_id = uuid4()
        mock_session = AsyncMock()

        repo = PendingDisclosureRepository(mock_session)
        count = await repo.stage_disclosures(poll_id, [])

        assert count == 0
        mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# PendingDisclosureRepository.get_unprocessed
# ---------------------------------------------------------------------------


class TestGetUnprocessed:
    """Tests for PendingDisclosureRepository.get_unprocessed."""

    @pytest.mark.asyncio
    async def test_returns_unprocessed_rows(self) -> None:
        """get_unprocessed returns rows where processed=False and poll_id matches."""
        from stockvaluefinder.pipeline.disclosure_repo import (
            PendingDisclosureRepository,
        )

        poll_id = uuid4()

        row1 = MagicMock(spec=PendingDisclosureDB)
        row1.processed = False
        row1.poll_id = poll_id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [row1]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PendingDisclosureRepository(mock_session)
        result = await repo.get_unprocessed(poll_id)

        assert len(result) == 1
        assert result[0].processed is False


# ---------------------------------------------------------------------------
# PendingDisclosureRepository.mark_processed
# ---------------------------------------------------------------------------


class TestMarkProcessed:
    """Tests for PendingDisclosureRepository.mark_processed."""

    @pytest.mark.asyncio
    async def test_marks_rows_as_processed(self) -> None:
        """mark_processed sets processed=True and processed_at on given ids."""
        from stockvaluefinder.pipeline.disclosure_repo import (
            PendingDisclosureRepository,
        )

        ids = [str(uuid4()), str(uuid4())]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PendingDisclosureRepository(mock_session)
        count = await repo.mark_processed(ids)

        assert count == 2
        mock_session.execute.assert_awaited_once()
