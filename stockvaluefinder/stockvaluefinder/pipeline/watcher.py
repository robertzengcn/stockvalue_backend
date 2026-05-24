"""WatcherService for automated financial report disclosure monitoring.

This module implements the core disclosure polling engine that:
- Polls AKShare for disclosure schedules (D-01)
- Falls back to CNInfo per-stock queries when AKShare fails (D-02)
- Monitors all report types: annual, semi-annual, Q1, Q3 (D-03)
- Detects new reports via business_key lookup against pipeline_tasks (D-10)
- Detects amendments via disclosure_date comparison (D-06)
- Enqueues one arq job per new disclosure (D-12)
- Uses two-phase architecture: poll -> pending_disclosures -> process (D-11)
- Updates watcher_state each poll cycle (D-16)
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.disclosure_repo import PendingDisclosureRepository
from stockvaluefinder.pipeline.models import PendingDisclosureCreate
from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PollResult:
    """Result of a poll_disclosures cycle.

    Attributes:
        staged_count: Number of disclosures staged to pending_disclosures.
        akshare_success: Whether the AKShare primary poll succeeded.
        cninfo_fallback: Whether CNInfo fallback was used.
    """

    staged_count: int = 0
    akshare_success: bool = False
    cninfo_fallback: bool = False


@dataclass(frozen=True)
class ProcessResult:
    """Result of a process_disclosures cycle.

    Attributes:
        new_count: Number of new reports detected.
        amendment_count: Number of amended reports detected.
        skip_count: Number of already-processed reports skipped.
    """

    new_count: int = 0
    amendment_count: int = 0
    skip_count: int = 0


def get_current_report_periods(now: datetime) -> list[tuple[str, str, int]]:
    """Calculate which report periods to poll based on current month.

    Returns list of (period_str, report_type, fiscal_year) tuples.
    Annual reports are due Apr 30 -> poll Jan-Apr.
    Q1 reports are due Apr 30 -> poll Jan-Apr.
    Semi-annual reports are due Aug 31 -> poll Jul-Aug.
    Q3 reports are due Oct 31 -> poll Oct-Nov.
    December polls for early annual filers.

    Args:
        now: Current datetime (expected UTC).

    Returns:
        List of (period_str, report_type, fiscal_year) tuples.

    Examples:
        >>> from datetime import datetime, timezone
        >>> get_current_report_periods(datetime(2025, 2, 1, tzinfo=timezone.utc))
        [('2024\u5e74\u62a5', 'annual', 2024), ('2025\u4e00\u5b63', 'q1', 2025)]
    """
    year = now.year
    month = now.month
    periods: list[tuple[str, str, int]] = []

    if month <= 4:
        # Annual + Q1 reporting season
        periods.append((f"{year - 1}\u5e74\u62a5", "annual", year - 1))
        periods.append((f"{year}\u4e00\u5b63", "q1", year))
    elif month in (7, 8):
        # Semi-annual reporting season (reports due Aug 31)
        periods.append((f"{year}\u534a\u5e74\u62a5", "semi_annual", year))
    elif month in (10, 11):
        # Q3 reporting season
        periods.append((f"{year}\u4e09\u5b63", "q3", year))
    elif month == 12:
        # Dec: early annual reports may appear
        periods.append((f"{year - 1}\u5e74\u62a5", "annual", year - 1))
    # May, June, September: no active reporting periods

    return periods


def normalize_akshare_ticker(raw_code: str, exchange: str = "") -> str:
    """Convert AKShare stock code to project ticker format.

    AKShare returns bare 6-digit codes like '600519', '000001'.
    Project format requires '600519.SH', '000001.SZ'.

    Args:
        raw_code: 6-digit stock code from AKShare.
        exchange: Exchange name from AKShare (if available).

    Returns:
        Normalized ticker string (e.g., '600519.SH').
    """
    code = str(raw_code).strip().zfill(6)
    if exchange and "\u4e0a\u6d77" in exchange:
        return f"{code}.SH"
    if exchange and "\u6df1\u5733" in exchange:
        return f"{code}.SZ"
    # Fallback: infer from code prefix
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    return f"{code}.SZ"


def build_business_key(ticker: str, fiscal_year: int, report_type: str) -> str:
    """Construct business_key for pipeline task deduplication.

    Format: ticker:fiscal_year:report_type

    Args:
        ticker: Normalized stock ticker (e.g., '600519.SH').
        fiscal_year: Fiscal year of the report.
        report_type: Report type ('annual', 'semi_annual', 'q1', 'q3').

    Returns:
        Business key string (e.g., '600519.SH:2023:annual').
    """
    return f"{ticker}:{fiscal_year}:{report_type}"


class WatcherService:
    """Service for automated disclosure monitoring and processing.

    Implements the two-phase poll-process architecture:
    1. poll_disclosures: Poll AKShare/CNInfo, stage to pending_disclosures
    2. process_disclosures: Read staged data, detect new/amendment, enqueue

    Args:
        akshare_client: AKShare client for data source calls.
        session_factory: Async session factory for database operations.
        config: Pipeline configuration.
    """

    def __init__(
        self,
        akshare_client: AKShareClient,
        session_factory: async_sessionmaker[AsyncSession],
        config: PipelineConfig,
    ) -> None:
        """Initialize WatcherService.

        Args:
            akshare_client: AKShare client for data source calls.
            session_factory: Async session factory for database operations.
            config: Pipeline configuration.
        """
        self._akshare = akshare_client
        self._session_factory = session_factory
        self._config = config
        self._redis_pool = None

    async def poll_disclosures(self) -> PollResult:
        """Poll for newly disclosed financial reports.

        Steps:
        1. Get active tickers from watchlist
        2. If empty, log warning and return (D-14)
        3. Determine current report periods
        4. Poll AKShare for each period (D-01)
        5. Fall back to CNInfo per-stock if AKShare fails (D-02)
        6. Filter results by watchlist tickers
        7. Stage to pending_disclosures (D-11)
        8. Enqueue process_disclosures job
        9. Update watcher_state (D-16)

        This method never raises -- all errors are caught and logged
        to prevent the cron from crashing.

        Returns:
            PollResult with staged count and success flags.
        """
        akshare_success = False
        cninfo_fallback = False
        staged_count = 0

        try:
            async with self._session_factory() as session:
                # Step 1-2: Get active tickers
                tickers = await self._get_active_tickers(session)
                if not tickers:
                    logger.warning("Watchlist is empty, skipping poll (D-14)")
                    await self._update_watcher_state(
                        session, False, False, is_error=False
                    )
                    return PollResult(
                        staged_count=0,
                        akshare_success=False,
                        cninfo_fallback=False,
                    )

                # Step 3: Determine report periods
                now = datetime.now(timezone.utc)
                periods = get_current_report_periods(now)

                if not periods:
                    logger.debug("No active reporting periods for current month")
                    await self._update_watcher_state(
                        session, True, False, is_error=False
                    )
                    return PollResult(
                        staged_count=0,
                        akshare_success=True,
                        cninfo_fallback=False,
                    )

                # Step 4-6: Poll and filter
                all_disclosures: list[PendingDisclosureCreate] = []

                for period_str, report_type, fiscal_year in periods:
                    disclosures = await self._poll_period(
                        session, tickers, period_str, report_type, fiscal_year
                    )
                    if disclosures is not None:
                        akshare_success = True
                        all_disclosures.extend(disclosures)
                    else:
                        # AKShare failed, try CNInfo fallback per ticker
                        cninfo_disclosures = await self._poll_cninfo_fallback(
                            tickers, report_type, fiscal_year
                        )
                        if cninfo_disclosures:
                            cninfo_fallback = True
                            all_disclosures.extend(cninfo_disclosures)

                # Step 7: Stage disclosures
                if all_disclosures:
                    poll_id = uuid4()
                    staged_count = await self._stage_disclosures(
                        session, poll_id, all_disclosures
                    )

                    # Step 8: Enqueue process job
                    await self._enqueue_process_disclosures(str(poll_id))

                # Step 9: Update watcher state
                await self._update_watcher_state(
                    session, akshare_success, cninfo_fallback, is_error=False
                )
                await session.commit()

        except Exception as e:
            logger.error("Error in poll_disclosures: %s", e, exc_info=True)
            try:
                async with self._session_factory() as session:
                    await self._update_watcher_state(
                        session, akshare_success, cninfo_fallback, is_error=True
                    )
                    await session.commit()
            except Exception:
                logger.error("Failed to update watcher state after error")

        return PollResult(
            staged_count=staged_count,
            akshare_success=akshare_success,
            cninfo_fallback=cninfo_fallback,
        )

    async def process_disclosures(self, poll_id: str) -> ProcessResult:
        """Process staged disclosures: detect new/amendment/skip and enqueue.

        Steps:
        1. Read unprocessed rows from pending_disclosures
        2. For each disclosure:
           a. Build business_key (D-04)
           b. Check pipeline_tasks for existing business_key (D-10)
           c. New: create task + enqueue download_report (D-12)
           d. Amendment: create task with timestamp suffix (D-05, D-06)
           e. Skip: already processed
        3. Mark processed disclosures
        4. Return counts

        Args:
            poll_id: UUID of the poll cycle to process.

        Returns:
            ProcessResult with new, amendment, and skip counts.
        """
        new_count = 0
        amendment_count = 0
        skip_count = 0

        try:
            async with self._session_factory() as session:
                # Step 1: Get unprocessed disclosures
                disclosures = await self._get_unprocessed(session, poll_id)

                if not disclosures:
                    logger.debug("No unprocessed disclosures for poll %s", poll_id)
                    return ProcessResult()

                processed_ids: list[str] = []

                for disc in disclosures:
                    # Step 2a: Build business_key
                    business_key = build_business_key(
                        disc.ticker, disc.fiscal_year, disc.report_type
                    )

                    # Step 2b: Check existing
                    existing = await self._check_existing_task(session, business_key)

                    if existing is None:
                        # Step 2c: New report
                        task = await self._create_task(
                            session, disc.ticker, business_key
                        )
                        if task is not None:
                            await self._enqueue_download_job(str(task.task_id))
                            new_count += 1
                    elif self._is_amendment(disc, existing):
                        # Step 2d: Amendment
                        amended_key = f"{business_key}:amd:{disc.disclosure_date}"
                        task = await self._create_task(
                            session, disc.ticker, amended_key
                        )
                        if task is not None:
                            await self._enqueue_download_job(str(task.task_id))
                            amendment_count += 1
                    else:
                        # Step 2e: Skip
                        skip_count += 1

                    processed_ids.append(str(disc.disclosure_id))

                # Step 3: Mark processed
                if processed_ids:
                    await self._mark_processed(session, processed_ids)
                    await session.commit()

        except Exception as e:
            logger.error(
                "Error in process_disclosures for poll %s: %s",
                poll_id,
                e,
                exc_info=True,
            )

        logger.info(
            "Processed disclosures: %d new, %d amendments, %d skipped",
            new_count,
            amendment_count,
            skip_count,
        )
        return ProcessResult(
            new_count=new_count,
            amendment_count=amendment_count,
            skip_count=skip_count,
        )

    # -- Internal helper methods (patchable for testing) --

    async def _get_active_tickers(self, session: AsyncSession) -> list[str]:
        """Get active tickers from watchlist via repository."""
        repo = WatchlistRepository(session)
        return await repo.get_active_tickers()

    async def _update_watcher_state(
        self,
        session: AsyncSession,
        akshare_success: bool,
        cninfo_fallback: bool,
        is_error: bool,
    ) -> Any:
        """Update watcher state via repository."""
        from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

        repo = WatcherStateRepository(session)
        return await repo.update_state(
            last_akshare_success=akshare_success,
            last_cninfo_fallback=cninfo_fallback,
            is_error=is_error,
        )

    async def _stage_disclosures(
        self,
        session: AsyncSession,
        poll_id: Any,
        disclosures: list[PendingDisclosureCreate],
    ) -> int:
        """Stage disclosures via repository."""
        repo = PendingDisclosureRepository(session)
        return await repo.stage_disclosures(poll_id, disclosures)

    async def _enqueue_process_disclosures(self, poll_id: str) -> bool:
        """Enqueue process_disclosures arq job."""
        try:
            if self._redis_pool is not None:
                redis = self._redis_pool
                await redis.enqueue_job("process_disclosures", poll_id)
            else:
                from arq import create_pool
                from stockvaluefinder.config import get_arq_redis_settings

                redis = await create_pool(get_arq_redis_settings())
                await redis.enqueue_job("process_disclosures", poll_id)
                await redis.close()
            return True
        except Exception as e:
            logger.error("Failed to enqueue process_disclosures: %s", e)
            return False

    async def _get_unprocessed(self, session: AsyncSession, poll_id: str) -> list[Any]:
        """Get unprocessed disclosures via repository."""
        from uuid import UUID

        repo = PendingDisclosureRepository(session)
        return await repo.get_unprocessed(UUID(poll_id))

    async def _check_existing_task(
        self, session: AsyncSession, business_key: str
    ) -> Any:
        """Check for existing task by business_key via PipelineTaskRepository."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        repo = PipelineTaskRepository(session)
        return await repo.get_by_business_key(business_key)

    async def _create_task(
        self, session: AsyncSession, ticker: str, business_key: str
    ) -> Any:
        """Create a new pipeline task via PipelineTaskRepository."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        repo = PipelineTaskRepository(session)
        try:
            return await repo.create_task(ticker, business_key)
        except ValueError:
            logger.warning("Task already exists for key: %s", business_key)
            return None

    async def _enqueue_download_job(self, task_id: str) -> bool:
        """Enqueue download_report arq job for a task."""
        try:
            if self._redis_pool is not None:
                redis = self._redis_pool
                await redis.enqueue_job("download_report", task_id)
            else:
                from arq import create_pool
                from stockvaluefinder.config import get_arq_redis_settings

                redis = await create_pool(get_arq_redis_settings())
                await redis.enqueue_job("download_report", task_id)
                await redis.close()
            return True
        except Exception as e:
            logger.error("Failed to enqueue download_report for %s: %s", task_id, e)
            return False

    async def _mark_processed(
        self, session: AsyncSession, disclosure_ids: list[str]
    ) -> int:
        """Mark disclosures as processed via repository."""
        repo = PendingDisclosureRepository(session)
        return await repo.mark_processed(disclosure_ids)

    def _is_amendment(self, disclosure: Any, existing_task: Any) -> bool:
        """Check if a disclosure is an amendment (later disclosure_date).

        An amendment is detected when the new disclosure has a later
        disclosure_date than the existing task (D-06).

        Args:
            disclosure: Pending disclosure with disclosure_date attribute.
            existing_task: Existing pipeline task with disclosure_date.

        Returns:
            True if this is an amendment (later disclosure_date).
        """
        new_date = getattr(disclosure, "disclosure_date", None)
        existing_date = getattr(existing_task, "disclosure_date", None)

        if new_date is None or existing_date is None:
            return False

        return new_date > existing_date

    async def _poll_period(
        self,
        session: AsyncSession,
        tickers: list[str],
        period_str: str,
        report_type: str,
        fiscal_year: int,
    ) -> list[PendingDisclosureCreate] | None:
        """Poll AKShare for a single period. Returns None on failure."""
        try:
            raw_rows = await self._akshare.get_report_disclosures(period_str)
            return self._filter_and_convert(raw_rows, tickers, report_type, fiscal_year)
        except Exception as e:
            logger.warning("AKShare poll failed for period %s: %s", period_str, e)
            return None

    async def _poll_cninfo_fallback(
        self,
        tickers: list[str],
        report_type: str,
        fiscal_year: int,
    ) -> list[PendingDisclosureCreate]:
        """Fall back to CNInfo per-stock queries (D-02)."""
        disclosures: list[PendingDisclosureCreate] = []
        # Map report_type to CNInfo category
        category_map = {
            "annual": "\u5e74\u62a5",
            "semi_annual": "\u534a\u5e74\u62a5",
            "q1": "\u4e00\u5b63\u62a5",
            "q3": "\u4e09\u5b63\u62a5",
        }
        category = category_map.get(report_type, "")

        for ticker in tickers:
            try:
                # Extract bare code from ticker (600519.SH -> 600519)
                bare_code = ticker.split(".")[0]
                raw_rows = await self._akshare.get_cninfo_announcements(
                    symbol=bare_code,
                    category=category,
                )
                converted = self._convert_cninfo_rows(
                    raw_rows, ticker, report_type, fiscal_year
                )
                disclosures.extend(converted)
            except Exception as e:
                logger.warning("CNInfo fallback failed for %s: %s", ticker, e)

        return disclosures

    def _filter_and_convert(
        self,
        raw_rows: list[dict[str, Any]],
        tickers: list[str],
        report_type: str,
        fiscal_year: int,
    ) -> list[PendingDisclosureCreate]:
        """Convert AKShare raw rows to PendingDisclosureCreate, filtered by watchlist."""
        ticker_set = set(tickers)
        disclosures: list[PendingDisclosureCreate] = []

        for row in raw_rows:
            raw_code = str(row.get("\u80a1\u7968\u4ee3\u7801", ""))
            ticker = normalize_akshare_ticker(raw_code)

            if ticker not in ticker_set:
                continue

            # Extract actual disclosure date
            actual_date = row.get("\u5b9e\u9645\u62ab\u9732")
            if actual_date is None:
                continue
            if isinstance(actual_date, str):
                try:
                    actual_date = date.fromisoformat(actual_date)
                except (ValueError, TypeError):
                    continue

            # Extract first appointment date
            first_appt = row.get("\u9996\u6b21\u9884\u7ea6")
            if isinstance(first_appt, str):
                try:
                    first_appt = date.fromisoformat(first_appt)
                except (ValueError, TypeError):
                    first_appt = None

            stock_name = str(row.get("\u80a1\u7968\u540d\u79f0", ""))

            disclosures.append(
                PendingDisclosureCreate(
                    ticker=ticker,
                    stock_name=stock_name or None,
                    report_type=report_type,  # type: ignore[arg-type]
                    fiscal_year=fiscal_year,
                    disclosure_date=actual_date
                    if isinstance(actual_date, date)
                    else None,
                    first_appointment=first_appt
                    if isinstance(first_appt, date)
                    else None,
                    source="akshare",
                    source_raw=row,
                )
            )

        return disclosures

    def _convert_cninfo_rows(
        self,
        raw_rows: list[dict[str, Any]],
        ticker: str,
        report_type: str,
        fiscal_year: int,
    ) -> list[PendingDisclosureCreate]:
        """Convert CNInfo raw rows to PendingDisclosureCreate."""
        disclosures: list[PendingDisclosureCreate] = []

        for row in raw_rows:
            # Extract date from 公告时间
            ann_time = row.get("\u516c\u544a\u65f6\u95f4")
            disclosure_date: date | None = None
            if isinstance(ann_time, datetime):
                disclosure_date = ann_time.date()
            elif isinstance(ann_time, str):
                try:
                    disclosure_date = date.fromisoformat(ann_time[:10])
                except (ValueError, TypeError):
                    pass

            stock_name = str(row.get("\u7b80\u79f0", ""))

            disclosures.append(
                PendingDisclosureCreate(
                    ticker=ticker,
                    stock_name=stock_name or None,
                    report_type=report_type,  # type: ignore[arg-type]
                    fiscal_year=fiscal_year,
                    disclosure_date=disclosure_date,
                    first_appointment=None,
                    source="cninfo",
                    source_raw=row,
                )
            )

        return disclosures


__all__ = [
    "PollResult",
    "ProcessResult",
    "WatcherService",
    "build_business_key",
    "get_current_report_periods",
    "normalize_akshare_ticker",
]
