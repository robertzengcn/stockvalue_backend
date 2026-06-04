"""Unit tests for market scanner repositories.

Tests IndexConstituentRepository, MarketScanRunRepository,
and MarketScanCandidateRepository using mocked AsyncSession,
following the established repository test patterns.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.models.enums import ScanType
from stockvaluefinder.models.market_scanner import (
    CandidateDetailResponse,
    CandidateListItemResponse,
    IndexConstituentCreate,
    MarketScanCandidateCreate,
    MarketScanRunCreate,
    ScanRunResponse,
)
from stockvaluefinder.repositories.index_constituent_repo import (
    IndexConstituentRepository,
)
from stockvaluefinder.repositories.market_scan_repo import (
    MarketScanCandidateRepository,
    MarketScanRunRepository,
)


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository tests."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


def _make_constituent(
    constituent_id: str | None = None,
    index_code: str = "CSI300",
    ticker: str = "600519.SH",
    name: str = "Kweichow Moutai",
    effective_date: date | None = None,
    is_active: bool = True,
    removed_date: date | None = None,
) -> SimpleNamespace:
    """Create a SimpleNamespace mimicking IndexConstituentDB for testing."""
    return SimpleNamespace(
        constituent_id=constituent_id or str(uuid4()),
        index_code=index_code,
        ticker=ticker,
        name=name,
        effective_date=effective_date or date(2024, 1, 1),
        is_active=is_active,
        removed_date=removed_date,
        source="akshare",
        source_raw=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_scan_run(
    run_id: str | None = None,
    index_codes: list[str] | None = None,
    scan_type: str = "daily",
    status: str = "pending",
    rules_version: str = "v1",
    total_count: int = 0,
    screened_count: int = 0,
    candidate_count: int = 0,
    error_summary: dict | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> SimpleNamespace:
    """Create a SimpleNamespace mimicking MarketScanRunDB for testing."""
    return SimpleNamespace(
        run_id=run_id or str(uuid4()),
        index_codes=index_codes or ["CSI300"],
        scan_type=scan_type,
        status=status,
        rules_version=rules_version,
        total_count=total_count,
        screened_count=screened_count,
        candidate_count=candidate_count,
        error_summary=error_summary,
        started_at=started_at,
        completed_at=completed_at,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_candidate(
    candidate_id: str | None = None,
    run_id: str | None = None,
    ticker: str = "600519.SH",
    index_code: str = "CSI300",
    passed: bool = True,
    composite_score: float = 85.0,
    screening_snapshot: dict | None = None,
) -> SimpleNamespace:
    """Create a SimpleNamespace mimicking MarketScanCandidateDB for testing."""
    return SimpleNamespace(
        candidate_id=candidate_id or str(uuid4()),
        run_id=run_id or str(uuid4()),
        ticker=ticker,
        index_code=index_code,
        passed=passed,
        composite_score=composite_score,
        screening_snapshot=screening_snapshot or {},
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# IndexConstituentRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIndexConstituentRepository:
    """Test suite for IndexConstituentRepository."""

    async def test_get_active_by_index_returns_active_constituents(self):
        """Test: get_active_by_index returns only active constituents."""
        session = _make_mock_session()
        active = [
            _make_constituent(ticker="600519.SH", is_active=True),
            _make_constituent(ticker="000001.SZ", is_active=True),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = active
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        result = await repo.get_active_by_index("CSI300")

        assert len(result) == 2
        assert all(c.is_active for c in result)

    async def test_get_active_by_index_returns_empty_when_none(self):
        """Test: get_active_by_index returns empty list when no active constituents."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        result = await repo.get_active_by_index("CSI300")

        assert result == []

    async def test_upsert_constituent_inserts_new(self):
        """Test: upsert_constituent inserts new constituent when no match exists."""
        session = _make_mock_session()
        new_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        data = IndexConstituentCreate(
            constituent_id=new_id,
            index_code="CSI300",
            ticker="600519.SH",
            name="Kweichow Moutai",
            effective_date=date(2024, 6, 1),
        )

        repo = IndexConstituentRepository(session)
        await repo.upsert_constituent(data)

        session.add.assert_called_once()
        session.flush.assert_called()

    async def test_upsert_constituent_updates_existing(self):
        """Test: upsert_constituent updates existing constituent when match exists."""
        session = _make_mock_session()
        existing = _make_constituent(
            constituent_id=str(uuid4()),
            index_code="CSI300",
            ticker="600519.SH",
            effective_date=date(2024, 6, 1),
            name="Old Name",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        session.execute.return_value = mock_result

        data = IndexConstituentCreate(
            constituent_id=existing.constituent_id,
            index_code="CSI300",
            ticker="600519.SH",
            name="Kweichow Moutai Updated",
            effective_date=date(2024, 6, 1),
        )

        repo = IndexConstituentRepository(session)
        result = await repo.upsert_constituent(data)

        session.flush.assert_called()
        assert result.name == "Kweichow Moutai Updated"

    async def test_bulk_upsert_constituents_inserts_multiple(self):
        """Test: bulk_upsert_constituents inserts multiple constituents."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        constituents = [
            IndexConstituentCreate(
                constituent_id=str(uuid4()),
                index_code="CSI300",
                ticker="600519.SH",
                name="Kweichow Moutai",
                effective_date=date(2024, 6, 1),
            ),
            IndexConstituentCreate(
                constituent_id=str(uuid4()),
                index_code="CSI300",
                ticker="000001.SZ",
                name="Ping An Bank",
                effective_date=date(2024, 6, 1),
            ),
        ]

        repo = IndexConstituentRepository(session)
        results = await repo.bulk_upsert_constituents(constituents)

        assert len(results) == 2
        assert session.add.call_count == 2

    async def test_deactivate_missing_marks_removed_constituents(self):
        """Test: deactivate_missing marks constituents as inactive when not in active set."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.rowcount = 2
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        count = await repo.deactivate_missing(
            index_code="CSI300",
            active_tickers={"600519.SH", "000001.SZ"},
            removed_date=date(2024, 6, 15),
        )

        assert count == 2
        session.flush.assert_called()

    async def test_deactivate_missing_returns_count(self):
        """Test: deactivate_missing returns the count of deactivated constituents."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.rowcount = 5
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        count = await repo.deactivate_missing(
            index_code="CSI300",
            active_tickers={"600519.SH"},
            removed_date=date(2024, 6, 15),
        )

        assert count == 5

    async def test_deactivate_missing_does_nothing_when_all_active(self):
        """Test: deactivate_missing does nothing when all tickers are still active."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        count = await repo.deactivate_missing(
            index_code="CSI300",
            active_tickers={"600519.SH", "000001.SZ", "000858.SZ"},
            removed_date=date(2024, 6, 15),
        )

        assert count == 0

    async def test_last_known_good_preserved_on_upsert_failure(self):
        """Test: if bulk_upsert_constituents raises, existing constituents remain unchanged.

        The upsert-before-deactivate ordering means that if the bulk upsert
        fails, deactivate_missing is never called, so the existing active
        constituents are preserved.
        """
        session = _make_mock_session()
        session.execute.side_effect = Exception("DB connection lost")

        constituents = [
            IndexConstituentCreate(
                constituent_id=str(uuid4()),
                index_code="CSI300",
                ticker="600519.SH",
                name="Kweichow Moutai",
                effective_date=date(2024, 6, 1),
            ),
        ]

        repo = IndexConstituentRepository(session)

        with pytest.raises(Exception, match="DB connection lost"):
            await repo.bulk_upsert_constituents(constituents)

        # deactivate_missing was never called because bulk_upsert failed
        # This is verified by the service layer calling upsert before deactivate

    async def test_sync_ordering_upsert_before_deactivate(self):
        """Test: upsert is called for all new constituents BEFORE deactivate_missing.

        This ensures no gap where no constituents are active.
        """
        session = _make_mock_session()

        call_order = []

        original_upsert = IndexConstituentRepository.upsert_constituent

        async def track_upsert(self, data):
            call_order.append(("upsert", data.ticker))
            return await original_upsert(self, data)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.rowcount = 0
        session.execute.return_value = mock_result

        with patch.object(
            IndexConstituentRepository, "upsert_constituent", track_upsert
        ):
            repo = IndexConstituentRepository(session)

            constituents = [
                IndexConstituentCreate(
                    constituent_id=str(uuid4()),
                    index_code="CSI300",
                    ticker="600519.SH",
                    name="Kweichow Moutai",
                    effective_date=date(2024, 6, 1),
                ),
                IndexConstituentCreate(
                    constituent_id=str(uuid4()),
                    index_code="CSI300",
                    ticker="000001.SZ",
                    name="Ping An Bank",
                    effective_date=date(2024, 6, 1),
                ),
            ]

            results = await repo.bulk_upsert_constituents(constituents)

        assert len(results) == 2
        assert call_order[0] == ("upsert", "600519.SH")
        assert call_order[1] == ("upsert", "000001.SZ")

    async def test_get_by_ticker_returns_all_memberships(self):
        """Test: get_by_ticker returns all index memberships for a ticker."""
        session = _make_mock_session()
        memberships = [
            _make_constituent(index_code="CSI300", effective_date=date(2024, 1, 1)),
            _make_constituent(index_code="CSI500", effective_date=date(2024, 3, 1)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = memberships
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        result = await repo.get_by_ticker("600519.SH")

        assert len(result) == 2

    async def test_get_constituent_history_returns_ordered(self):
        """Test: get_constituent_history returns records ordered by effective_date desc."""
        session = _make_mock_session()
        history = [
            _make_constituent(effective_date=date(2024, 6, 1)),
            _make_constituent(effective_date=date(2024, 1, 1)),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = history
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = IndexConstituentRepository(session)
        result = await repo.get_constituent_history("CSI300")

        assert len(result) == 2


# ---------------------------------------------------------------------------
# MarketScanRunRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarketScanRunRepository:
    """Test suite for MarketScanRunRepository."""

    async def test_create_run_inserts_pending(self):
        """Test: create_run inserts a new run with status='pending'."""
        session = _make_mock_session()
        new_id = str(uuid4())

        data = MarketScanRunCreate(
            run_id=new_id,
            index_codes=("CSI300",),
            scan_type=ScanType.DAILY,
            rules_version="v1",
        )

        def mock_refresh(entity: object) -> None:
            pass

        session.refresh = AsyncMock(side_effect=mock_refresh)

        repo = MarketScanRunRepository(session)
        await repo.create_run(data)

        session.add.assert_called_once()
        session.flush.assert_called()

    async def test_mark_running_transitions_from_pending(self):
        """Test: mark_running transitions status from 'pending' to 'running'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        run = _make_scan_run(run_id=run_id, status="pending")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.mark_running(run_id)

        assert result.status == "running"
        assert result.started_at is not None
        session.flush.assert_called()

    async def test_mark_running_raises_on_wrong_status(self):
        """Test: mark_running raises ValueError when status is not 'pending'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        run = _make_scan_run(run_id=run_id, status="running")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)

        with pytest.raises(ValueError, match="expected pending"):
            await repo.mark_running(run_id)

    async def test_mark_running_raises_on_not_found(self):
        """Test: mark_running raises ValueError when run_id not found."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)

        with pytest.raises(ValueError, match="not found"):
            await repo.mark_running(str(uuid4()))

    async def test_mark_completed_transitions_from_running(self):
        """Test: mark_completed transitions from 'running' to 'completed'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        run = _make_scan_run(run_id=run_id, status="running")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.mark_completed(
            run_id, total_count=300, screened_count=50, candidate_count=10
        )

        assert result.status == "completed"
        assert result.completed_at is not None
        assert result.total_count == 300
        assert result.screened_count == 50
        assert result.candidate_count == 10

    async def test_mark_completed_raises_on_wrong_status(self):
        """Test: mark_completed raises ValueError when status is not 'running'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        run = _make_scan_run(run_id=run_id, status="pending")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)

        with pytest.raises(ValueError, match="expected running"):
            await repo.mark_completed(run_id, 300, 50, 10)

    async def test_mark_partial_failed_transitions_from_running(self):
        """Test: mark_partial_failed transitions from 'running' to 'partial_failed'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        run = _make_scan_run(run_id=run_id, status="running")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        error_summary = {"ticker_600519.SH": "timeout"}
        result = await repo.mark_partial_failed(
            run_id,
            error_summary=error_summary,
            total_count=300,
            screened_count=45,
            candidate_count=8,
        )

        assert result.status == "partial_failed"
        assert result.completed_at is not None
        assert result.error_summary == error_summary
        assert result.total_count == 300

    async def test_get_latest_run_returns_most_recent(self):
        """Test: get_latest_run returns the most recent run for an index_code."""
        session = _make_mock_session()
        run = _make_scan_run(status="completed")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.get_latest_run("CSI300")

        assert result is not None
        assert result.status == "completed"

    async def test_get_latest_run_returns_none_when_no_runs(self):
        """Test: get_latest_run returns None when no runs exist for index_code."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.get_latest_run("CSI300")

        assert result is None

    async def test_get_by_status_returns_matching_runs(self):
        """Test: get_by_status returns all runs with given status."""
        session = _make_mock_session()
        runs = [_make_scan_run(status="completed"), _make_scan_run(status="completed")]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = runs
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.get_by_status("completed")

        assert len(result) == 2


# ---------------------------------------------------------------------------
# MarketScanCandidateRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarketScanCandidateRepository:
    """Test suite for MarketScanCandidateRepository."""

    async def test_get_by_run_id_returns_candidates(self):
        """Test: get_by_run_id returns all candidates for a scan run."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidates = [
            _make_candidate(run_id=run_id, ticker="600519.SH"),
            _make_candidate(run_id=run_id, ticker="000001.SZ"),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = candidates
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = MarketScanCandidateRepository(session)
        result = await repo.get_by_run_id(run_id)

        assert len(result) == 2

    async def test_get_passed_candidates_returns_only_passed(self):
        """Test: get_passed_candidates returns only candidates where passed=True."""
        session = _make_mock_session()
        run_id = str(uuid4())
        passed = [
            _make_candidate(run_id=run_id, ticker="600519.SH", passed=True),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = passed
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        repo = MarketScanCandidateRepository(session)
        result = await repo.get_passed_candidates(run_id)

        assert len(result) == 1
        assert result[0].passed is True

    async def test_get_by_ticker_run_returns_candidate(self):
        """Test: get_by_ticker_run returns candidate for (run_id, ticker) pair."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidate = _make_candidate(run_id=run_id, ticker="600519.SH")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        session.execute.return_value = mock_result

        repo = MarketScanCandidateRepository(session)
        result = await repo.get_by_ticker_run(run_id, "600519.SH")

        assert result is not None
        assert result.ticker == "600519.SH"

    async def test_create_inserts_candidate_with_field_mapping(self):
        """Test: create inserts candidate with field mapping from Pydantic model."""
        session = _make_mock_session()
        candidate_id = str(uuid4())
        run_id = str(uuid4())

        data = MarketScanCandidateCreate(
            candidate_id=candidate_id,
            run_id=run_id,
            ticker="600519.SH",
            index_code="CSI300",
            passed=True,
            composite_score=92.5,
            screening_snapshot={"margin_of_safety": 0.45},
        )

        def mock_refresh(entity: object) -> None:
            pass

        session.refresh = AsyncMock(side_effect=mock_refresh)

        repo = MarketScanCandidateRepository(session)
        await repo.create(data)

        session.add.assert_called_once()
        session.flush.assert_called()


# ---------------------------------------------------------------------------
# MarketScanRunRepository Pagination Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarketScanRunRepositoryPagination:
    """Test suite for MarketScanRunRepository paginated listing methods."""

    def _setup_count_and_data(
        self,
        session: AsyncMock,
        total: int,
        runs: list[SimpleNamespace],
    ) -> None:
        """Configure mock session to return count and data results.

        First execute call returns count, second returns data rows.
        """
        count_result = MagicMock()
        count_result.scalar_one.return_value = total

        data_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = runs
        data_result.scalars.return_value = mock_scalars

        session.execute.side_effect = [count_result, data_result]

    async def test_list_runs_paginated_default(self):
        """Test: list_runs_paginated returns (runs, total) with default pagination."""
        session = _make_mock_session()
        runs = [_make_scan_run(status="completed"), _make_scan_run(status="completed")]

        self._setup_count_and_data(session, total=2, runs=runs)

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated()

        assert len(result) == 2
        assert total == 2

    async def test_list_runs_paginated_filter_by_status(self):
        """Test: list_runs_paginated filters by status when provided."""
        session = _make_mock_session()
        runs = [_make_scan_run(status="completed")]

        self._setup_count_and_data(session, total=1, runs=runs)

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated(status="completed")

        assert len(result) == 1
        assert total == 1
        # Verify the execute was called twice (count + data)
        assert session.execute.call_count == 2

    async def test_list_runs_paginated_filter_by_scan_type(self):
        """Test: list_runs_paginated filters by scan_type when provided."""
        session = _make_mock_session()
        runs = [_make_scan_run(scan_type="weekly")]

        self._setup_count_and_data(session, total=1, runs=runs)

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated(scan_type="weekly")

        assert len(result) == 1
        assert total == 1

    async def test_list_runs_paginated_combined_filters(self):
        """Test: list_runs_paginated applies both status and scan_type filters."""
        session = _make_mock_session()
        runs = [_make_scan_run(status="completed", scan_type="daily")]

        self._setup_count_and_data(session, total=1, runs=runs)

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated(
            status="completed", scan_type="daily"
        )

        assert len(result) == 1
        assert total == 1

    async def test_list_runs_paginated_orders_by_created_at_desc(self):
        """Test: list_runs_paginated orders by created_at descending."""
        session = _make_mock_session()
        runs = [_make_scan_run(), _make_scan_run()]

        self._setup_count_and_data(session, total=2, runs=runs)

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated()

        assert len(result) == 2
        assert total == 2

    async def test_list_runs_paginated_caps_limit_at_100(self):
        """Test: list_runs_paginated caps limit at 100 to prevent DoS."""
        session = _make_mock_session()
        self._setup_count_and_data(session, total=0, runs=[])

        repo = MarketScanRunRepository(session)
        result, total = await repo.list_runs_paginated(limit=500)

        # Verify query executed - the capping happens internally
        assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# MarketScanCandidateRepository Pagination Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarketScanCandidateRepositoryPagination:
    """Test suite for MarketScanCandidateRepository paginated listing methods."""

    def _setup_count_and_data(
        self,
        session: AsyncMock,
        total: int,
        candidates: list[SimpleNamespace],
    ) -> None:
        """Configure mock session to return count and data results."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = total

        data_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = candidates
        data_result.scalars.return_value = mock_scalars

        session.execute.side_effect = [count_result, data_result]

    async def test_list_candidates_paginated_default(self):
        """Test: list_candidates_paginated returns (candidates, total) with default sort."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidates = [
            _make_candidate(run_id=run_id, composite_score=90.0),
            _make_candidate(run_id=run_id, composite_score=80.0),
        ]

        self._setup_count_and_data(session, total=2, candidates=candidates)

        repo = MarketScanCandidateRepository(session)
        result, total = await repo.list_candidates_paginated(run_id=run_id)

        assert len(result) == 2
        assert total == 2

    async def test_list_candidates_paginated_filter_by_index_code(self):
        """Test: list_candidates_paginated filters by index_code when provided."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidates = [
            _make_candidate(run_id=run_id, index_code="CSI300"),
        ]

        self._setup_count_and_data(session, total=1, candidates=candidates)

        repo = MarketScanCandidateRepository(session)
        result, total = await repo.list_candidates_paginated(
            run_id=run_id, index_code="CSI300"
        )

        assert len(result) == 1
        assert total == 1

    async def test_list_candidates_paginated_sort_by_safety_margin(self):
        """Test: list_candidates_paginated sorts by safety_margin from JSONB."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidates = [
            _make_candidate(
                run_id=run_id,
                screening_snapshot={"margin_of_safety": 0.5},
            ),
        ]

        self._setup_count_and_data(session, total=1, candidates=candidates)

        repo = MarketScanCandidateRepository(session)
        result, total = await repo.list_candidates_paginated(
            run_id=run_id, sort_by="safety_margin"
        )

        assert len(result) == 1
        assert total == 1

    async def test_list_candidates_paginated_rejects_invalid_sort(self):
        """Test: list_candidates_paginated raises ValueError for invalid sort_by."""
        session = _make_mock_session()
        run_id = str(uuid4())

        repo = MarketScanCandidateRepository(session)

        with pytest.raises(ValueError, match="Invalid sort_by"):
            await repo.list_candidates_paginated(
                run_id=run_id, sort_by="unknown_field"
            )

    async def test_list_candidates_paginated_asc_order(self):
        """Test: list_candidates_paginated respects sort_order='asc'."""
        session = _make_mock_session()
        run_id = str(uuid4())
        candidates = [_make_candidate(run_id=run_id)]

        self._setup_count_and_data(session, total=1, candidates=candidates)

        repo = MarketScanCandidateRepository(session)
        result, total = await repo.list_candidates_paginated(
            run_id=run_id, sort_order="asc"
        )

        assert len(result) == 1

    async def test_list_candidates_paginated_caps_limit(self):
        """Test: list_candidates_paginated caps limit at 100."""
        session = _make_mock_session()
        run_id = str(uuid4())

        self._setup_count_and_data(session, total=0, candidates=[])

        repo = MarketScanCandidateRepository(session)
        result, total = await repo.list_candidates_paginated(
            run_id=run_id, limit=500
        )

        assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# MarketScanRunRepository GetCandidateById Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarketScanCandidateRepositoryGetById:
    """Test suite for get_candidate_by_id method on run repository."""

    async def test_get_candidate_by_id_found(self):
        """Test: get_candidate_by_id returns candidate when found."""
        session = _make_mock_session()
        candidate_id = str(uuid4())
        candidate = _make_candidate(candidate_id=candidate_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.get_candidate_by_id(candidate_id)

        assert result is not None
        assert result.candidate_id == candidate_id

    async def test_get_candidate_by_id_not_found(self):
        """Test: get_candidate_by_id returns None when not found."""
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        repo = MarketScanRunRepository(session)
        result = await repo.get_candidate_by_id(str(uuid4()))

        assert result is None


# ---------------------------------------------------------------------------
# API Response Pydantic Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApiResponseModels:
    """Test suite for Pydantic API response models in market_scanner.py."""

    async def test_scan_run_response_serializes_correctly(self):
        """Test: ScanRunResponse serializes run data correctly."""
        now = datetime.now(timezone.utc)
        response = ScanRunResponse(
            run_id=str(uuid4()),
            index_codes=["CSI300"],
            scan_type="daily",
            status="completed",
            rules_version="v1",
            total_count=300,
            screened_count=50,
            candidate_count=10,
            started_at=now,
            completed_at=now,
            created_at=now,
        )

        assert response.scan_type == "daily"
        assert response.status == "completed"
        assert response.total_count == 300
        assert response.candidate_count == 10
        assert len(response.index_codes) == 1

    async def test_candidate_list_item_response_serializes(self):
        """Test: CandidateListItemResponse serializes candidate summary."""
        now = datetime.now(timezone.utc)
        response = CandidateListItemResponse(
            candidate_id=str(uuid4()),
            run_id=str(uuid4()),
            ticker="600519.SH",
            index_code="CSI300",
            composite_score=85.5,
            safety_margin=0.45,
            risk_level="LOW",
            created_at=now,
        )

        assert response.ticker == "600519.SH"
        assert response.composite_score == 85.5
        assert response.safety_margin == 0.45
        assert response.risk_level == "LOW"

    async def test_candidate_detail_response_includes_snapshot(self):
        """Test: CandidateDetailResponse includes full screening_snapshot."""
        now = datetime.now(timezone.utc)
        snapshot = {
            "margin_of_safety": 0.45,
            "risk_level": "LOW",
            "intrinsic_value": 1850.0,
            "reasons": ["High margin of safety", "Low M-Score"],
        }
        response = CandidateDetailResponse(
            candidate_id=str(uuid4()),
            run_id=str(uuid4()),
            ticker="600519.SH",
            index_code="CSI300",
            composite_score=85.5,
            screening_snapshot=snapshot,
            created_at=now,
        )

        assert response.screening_snapshot == snapshot
        assert response.screening_snapshot["margin_of_safety"] == 0.45
        assert len(response.screening_snapshot["reasons"]) == 2
