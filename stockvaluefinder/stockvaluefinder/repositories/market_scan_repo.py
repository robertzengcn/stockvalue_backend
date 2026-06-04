"""Repositories for Market Scan Run and Candidate data access.

Contains two repository classes:
    - MarketScanRunRepository: Scan run lifecycle with state machine transitions
    - MarketScanCandidateRepository: Per-stock screening result queries
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.market_scan import (
    MarketScanCandidateDB,
    MarketScanRunDB,
)
from stockvaluefinder.models.market_scanner import (
    MarketScanCandidateCreate,
    MarketScanCandidateUpdate,
    MarketScanRunCreate,
    MarketScanRunUpdate,
)
from stockvaluefinder.repositories.base import BaseRepository


class MarketScanRunRepository(
    BaseRepository[MarketScanRunDB, MarketScanRunCreate, MarketScanRunUpdate]
):
    """Repository for MarketScanRun data access with state machine transitions.

    Manages the scan run lifecycle: pending -> running -> completed / partial_failed.
    Each transition validates the current state before allowing the change (EXE-04).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with MarketScanRunDB model.

        Args:
            session: Async database session
        """
        super().__init__(MarketScanRunDB, session)

    async def create_run(
        self,
        data: MarketScanRunCreate,
    ) -> MarketScanRunDB:
        """Create a new scan run with status='pending'.

        Overrides base create to map Pydantic fields to ORM columns,
        converting index_codes tuple to list for JSONB storage.

        Args:
            data: MarketScanRunCreate Pydantic model

        Returns:
            Created MarketScanRunDB instance with status='pending'
        """
        db_obj = MarketScanRunDB(
            run_id=data.run_id,
            index_codes=list(data.index_codes),
            scan_type=data.scan_type.value
            if hasattr(data.scan_type, "value")
            else data.scan_type,
            status="pending",
            rules_version=data.rules_version,
            total_count=data.total_count,
            screened_count=data.screened_count,
            candidate_count=data.candidate_count,
            error_summary=data.error_summary,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def mark_running(
        self,
        run_id: UUID,
    ) -> MarketScanRunDB:
        """Transition run from 'pending' to 'running'.

        Validates that the run exists and is currently in 'pending' state.

        Args:
            run_id: UUID of the scan run

        Returns:
            Updated MarketScanRunDB with status='running'

        Raises:
            ValueError: If run not found or not in 'pending' state
        """
        stmt = select(MarketScanRunDB).where(
            MarketScanRunDB.run_id == run_id,
        )
        result = await self._session.execute(stmt)
        run = result.scalar_one_or_none()

        if run is None:
            raise ValueError(f"Run {run_id} not found")
        if run.status != "pending":
            raise ValueError(f"Run {run_id} is {run.status}, expected pending")

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def mark_completed(
        self,
        run_id: UUID,
        total_count: int,
        screened_count: int,
        candidate_count: int,
    ) -> MarketScanRunDB:
        """Transition run from 'running' to 'completed'.

        Validates that the run exists and is currently in 'running' state.
        Updates count fields and sets completed_at timestamp.

        Args:
            run_id: UUID of the scan run
            total_count: Total number of stocks in scan pool
            screened_count: Number of stocks passing coarse screen
            candidate_count: Number of final candidates

        Returns:
            Updated MarketScanRunDB with status='completed'

        Raises:
            ValueError: If run not found or not in 'running' state
        """
        stmt = select(MarketScanRunDB).where(
            MarketScanRunDB.run_id == run_id,
        )
        result = await self._session.execute(stmt)
        run = result.scalar_one_or_none()

        if run is None:
            raise ValueError(f"Run {run_id} not found")
        if run.status != "running":
            raise ValueError(f"Run {run_id} is {run.status}, expected running")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.total_count = total_count
        run.screened_count = screened_count
        run.candidate_count = candidate_count
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def mark_partial_failed(
        self,
        run_id: UUID,
        error_summary: dict[str, Any],
        total_count: int | None = None,
        screened_count: int | None = None,
        candidate_count: int | None = None,
    ) -> MarketScanRunDB:
        """Transition run from 'running' to 'partial_failed'.

        Validates that the run exists and is currently in 'running' state.
        Records error_summary JSONB and optionally updates count fields.

        Args:
            run_id: UUID of the scan run
            error_summary: JSONB summary of errors encountered
            total_count: Optional updated total count
            screened_count: Optional updated screened count
            candidate_count: Optional updated candidate count

        Returns:
            Updated MarketScanRunDB with status='partial_failed'

        Raises:
            ValueError: If run not found or not in 'running' state
        """
        stmt = select(MarketScanRunDB).where(
            MarketScanRunDB.run_id == run_id,
        )
        result = await self._session.execute(stmt)
        run = result.scalar_one_or_none()

        if run is None:
            raise ValueError(f"Run {run_id} not found")
        if run.status != "running":
            raise ValueError(f"Run {run_id} is {run.status}, expected running")

        run.status = "partial_failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_summary = error_summary
        if total_count is not None:
            run.total_count = total_count
        if screened_count is not None:
            run.screened_count = screened_count
        if candidate_count is not None:
            run.candidate_count = candidate_count
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def get_latest_run(
        self,
        index_code: str,
    ) -> MarketScanRunDB | None:
        """Get the most recent run for a given index code.

        Uses JSONB contains to match runs where the index_codes array
        contains the specified index_code.

        Args:
            index_code: Index pool identifier to search for

        Returns:
            Most recent MarketScanRunDB or None if no runs exist
        """
        from sqlalchemy import func, text

        stmt = (
            select(MarketScanRunDB)
            .where(
                func.jsonb_path_exists(
                    MarketScanRunDB.index_codes,
                    text(f"'$[*] ? (@ == \"{index_code}\")'"),
                )
            )
            .order_by(MarketScanRunDB.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: str,
        limit: int = 50,
    ) -> list[MarketScanRunDB]:
        """Get all runs with a given status, ordered by created_at desc.

        Args:
            status: Lifecycle status to filter by
            limit: Maximum number of runs to return

        Returns:
            List of MarketScanRunDB objects with the given status
        """
        stmt = (
            select(MarketScanRunDB)
            .where(MarketScanRunDB.status == status)
            .order_by(MarketScanRunDB.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_runs_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        scan_type: str | None = None,
    ) -> tuple[list[MarketScanRunDB], int]:
        """List scan runs with pagination and optional filters.

        Args:
            page: Page number (1-based).
            limit: Items per page (capped at 100).
            status: Optional status filter (pending, running, completed, partial_failed).
            scan_type: Optional scan type filter (daily, weekly).

        Returns:
            Tuple of (list of runs, total count matching filters).
        """
        capped_limit = min(limit, 100)
        filters: list[Any] = []
        if status is not None:
            filters.append(MarketScanRunDB.status == status)
        if scan_type is not None:
            filters.append(MarketScanRunDB.scan_type == scan_type)

        count_stmt = select(func.count()).select_from(MarketScanRunDB)
        for f in filters:
            count_stmt = count_stmt.where(f)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        data_stmt = select(MarketScanRunDB)
        for f in filters:
            data_stmt = data_stmt.where(f)
        data_stmt = (
            data_stmt.order_by(MarketScanRunDB.created_at.desc())
            .offset((page - 1) * capped_limit)
            .limit(capped_limit)
        )
        data_result = await self._session.execute(data_stmt)
        runs = list(data_result.scalars().all())

        return runs, total

    async def get_candidate_by_id(
        self,
        candidate_id: UUID,
    ) -> MarketScanCandidateDB | None:
        """Get a single candidate by its candidate_id.

        Args:
            candidate_id: UUID of the candidate record.

        Returns:
            MarketScanCandidateDB if found, None otherwise.
        """
        stmt = select(MarketScanCandidateDB).where(
            MarketScanCandidateDB.candidate_id == candidate_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class MarketScanCandidateRepository(
    BaseRepository[
        MarketScanCandidateDB, MarketScanCandidateCreate, MarketScanCandidateUpdate
    ]
):
    """Repository for MarketScanCandidate data access.

    Provides query methods for scan candidates, including filtering
    by run, pass status, and specific (run_id, ticker) lookups.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with MarketScanCandidateDB model.

        Args:
            session: Async database session
        """
        super().__init__(MarketScanCandidateDB, session)

    async def get_by_run_id(
        self,
        run_id: UUID,
    ) -> list[MarketScanCandidateDB]:
        """Get all candidates for a given scan run.

        Args:
            run_id: UUID of the scan run

        Returns:
            List of MarketScanCandidateDB objects ordered by composite_score desc
        """
        stmt = (
            select(MarketScanCandidateDB)
            .where(MarketScanCandidateDB.run_id == run_id)
            .order_by(MarketScanCandidateDB.composite_score.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_passed_candidates(
        self,
        run_id: UUID,
    ) -> list[MarketScanCandidateDB]:
        """Get only candidates that passed all screening layers.

        Args:
            run_id: UUID of the scan run

        Returns:
            List of MarketScanCandidateDB where passed=True, ordered by score desc
        """
        stmt = (
            select(MarketScanCandidateDB)
            .where(
                MarketScanCandidateDB.run_id == run_id,
                MarketScanCandidateDB.passed.is_(True),
            )
            .order_by(MarketScanCandidateDB.composite_score.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker_run(
        self,
        run_id: UUID,
        ticker: str,
    ) -> MarketScanCandidateDB | None:
        """Get candidate for a specific (run_id, ticker) pair.

        Args:
            run_id: UUID of the scan run
            ticker: Stock code (e.g., 600519.SH)

        Returns:
            MarketScanCandidateDB if found, None otherwise
        """
        stmt = (
            select(MarketScanCandidateDB)
            .where(
                MarketScanCandidateDB.run_id == run_id,
                MarketScanCandidateDB.ticker == ticker,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        data: MarketScanCandidateCreate,
    ) -> MarketScanCandidateDB:
        """Create a new scan candidate record.

        Overrides base create to map Pydantic fields to ORM columns.

        Args:
            data: MarketScanCandidateCreate Pydantic model

        Returns:
            Created MarketScanCandidateDB instance
        """
        db_obj = MarketScanCandidateDB(
            candidate_id=data.candidate_id,
            run_id=data.run_id,
            ticker=data.ticker,
            index_code=data.index_code,
            passed=data.passed,
            composite_score=data.composite_score,
            screening_snapshot=data.screening_snapshot,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def list_candidates_paginated(
        self,
        run_id: UUID,
        page: int = 1,
        limit: int = 20,
        index_code: str | None = None,
        sort_by: str = "composite_score",
        sort_order: str = "desc",
    ) -> tuple[list[MarketScanCandidateDB], int]:
        """List candidates for a scan run with pagination and dynamic sorting.

        Args:
            run_id: UUID of the scan run.
            page: Page number (1-based).
            limit: Items per page (capped at 100).
            index_code: Optional index code filter.
            sort_by: Sort field (composite_score, safety_margin, created_at).
            sort_order: Sort direction (desc or asc).

        Returns:
            Tuple of (list of candidates, total count matching filters).

        Raises:
            ValueError: If sort_by is not a recognized field.
        """
        capped_limit = min(limit, 100)
        allowed_sort_fields = {"composite_score", "safety_margin", "created_at"}
        if sort_by not in allowed_sort_fields:
            raise ValueError(
                f"Invalid sort_by '{sort_by}'. "
                f"Allowed values: {sorted(allowed_sort_fields)}"
            )

        base_filters = [
            MarketScanCandidateDB.run_id == run_id,
            MarketScanCandidateDB.passed.is_(True),
        ]
        if index_code is not None:
            base_filters.append(MarketScanCandidateDB.index_code == index_code)

        count_stmt = select(func.count()).select_from(MarketScanCandidateDB)
        for f in base_filters:
            count_stmt = count_stmt.where(f)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        sort_map: dict[str, Any] = {
            "composite_score": MarketScanCandidateDB.composite_score,
            "safety_margin": text(
                "CAST(screening_snapshot->>'margin_of_safety' AS FLOAT)"
            ),
            "created_at": MarketScanCandidateDB.created_at,
        }
        sort_col = sort_map[sort_by]

        data_stmt = select(MarketScanCandidateDB)
        for f in base_filters:
            data_stmt = data_stmt.where(f)

        order_expr = desc(sort_col) if sort_order == "desc" else asc(sort_col)
        data_stmt = (
            data_stmt.order_by(order_expr)
            .offset((page - 1) * capped_limit)
            .limit(capped_limit)
        )
        data_result = await self._session.execute(data_stmt)
        candidates = list(data_result.scalars().all())

        return candidates, total
