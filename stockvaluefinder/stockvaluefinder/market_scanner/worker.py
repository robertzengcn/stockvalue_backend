"""Arq worker for scheduled market scans.

Defines the ScannerWorkerSettings class that configures an arq worker with:
- 1 job function: run_market_scan (manual and cron-triggered)
- 2 cron jobs: daily_light_scan (09:30 UTC weekdays), weekly_deep_scan (Sat 02:00 UTC)
- Redis connection settings (reuses get_arq_redis_settings from config)

The worker runs as a separate arq process alongside the existing pipeline worker.
ScanOrchestrator is instantiated per-invocation to ensure fresh sessions and
prevent stale database connections.

Concurrent scan prevention:
    Before starting a scan for any index_code, the job function checks
    MarketScanRunRepository.get_latest_run() for an already-running or
    pending scan. If found, the scan is skipped with a warning log.

Usage:
    arq stockvaluefinder.market_scanner.worker.ScannerWorkerSettings
"""

import logging
from dataclasses import replace
from typing import Any
from uuid import UUID

from arq import cron

from stockvaluefinder.config import get_arq_redis_settings
from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.market_scanner.batch_data_fetcher import BatchDataFetcher
from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.scan_orchestrator import ScanOrchestrator
from stockvaluefinder.models.enums import ScanType
from stockvaluefinder.repositories.index_constituent_repo import (
    IndexConstituentRepository,
)
from stockvaluefinder.repositories.market_scan_repo import (
    MarketScanCandidateRepository,
    MarketScanRunRepository,
)

logger = logging.getLogger(__name__)


async def _build_orchestrator(
    config: MarketScannerConfig,
    session: Any,
) -> ScanOrchestrator:
    """Build a ScanOrchestrator with all required dependencies.

    Instantiates ExternalDataService and initializes it before returning
    the orchestrator. The data_service initialization is required for
    AKShare client setup and fallback chain configuration.

    Args:
        config: Market scanner configuration with thresholds and weights.
        session: AsyncSession for repository construction.

    Returns:
        Fully initialized ScanOrchestrator ready to execute scans.
    """
    from stockvaluefinder.external.data_service import ExternalDataService

    data_service = ExternalDataService()
    await data_service.initialize()

    run_repo = MarketScanRunRepository(session)
    candidate_repo = MarketScanCandidateRepository(session)
    constituent_repo = IndexConstituentRepository(session)
    batch_fetcher = BatchDataFetcher()

    return ScanOrchestrator(
        config=config,
        data_service=data_service,
        run_repo=run_repo,
        candidate_repo=candidate_repo,
        constituent_repo=constituent_repo,
        batch_fetcher=batch_fetcher,
    )


async def run_market_scan(
    ctx: dict[str, Any],
    index_codes: list[str] | None = None,
    scan_type: str = "daily",
    top_n: int | None = None,
) -> dict[str, str]:
    """Run a market scan for the specified index codes.

    Can be called as an arq job function (via cron or manual enqueue).
    Creates a ScanOrchestrator per-invocation with a fresh database session.

    Concurrent scan prevention: checks get_latest_run() for each index_code
    before starting. If a run with status "running" or "pending" exists,
    that index is skipped with a warning log.

    Args:
        ctx: arq worker context dict (unused but required by arq signature).
        index_codes: Optional list of index codes to scan. Defaults to
            config.index_codes (CSI300, CSI500).
        scan_type: Scan frequency - "daily" or "weekly". Defaults to "daily".
        top_n: Optional override for top N stocks. Applied to daily_top_n
            or weekly_top_n depending on scan_type.

    Returns:
        Dict with "status" key: "completed" on success, "failed" on exception.
        On failure, includes "error" key with exception message.
    """
    try:
        scan_type_enum = ScanType(scan_type)
    except ValueError:
        logger.error(f"Invalid scan_type: {scan_type}")
        return {"status": "failed", "error": f"Invalid scan_type: {scan_type}"}

    config = MarketScannerConfig()

    if top_n is not None:
        if scan_type_enum == ScanType.DAILY:
            config = replace(config, daily_top_n=top_n)
        else:
            config = replace(config, weekly_top_n=top_n)

    codes_to_scan = tuple(index_codes) if index_codes else config.index_codes

    try:
        async with async_session_maker() as session:
            for index_code in codes_to_scan:
                run_repo = MarketScanRunRepository(session)
                latest_run = await run_repo.get_latest_run(index_code)

                if latest_run is not None and latest_run.status in (
                    "running",
                    "pending",
                ):
                    logger.warning(
                        f"Skipping {scan_type} scan for {index_code}: "
                        f"run {latest_run.run_id} is {latest_run.status}"
                    )
                    continue

                orchestrator = await _build_orchestrator(config, session)
                run_id: UUID = await orchestrator.run_scan(
                    index_code,
                    scan_type_enum,
                )
                await session.commit()
                logger.info(
                    f"{scan_type.capitalize()} scan completed: "
                    f"{index_code} run_id={run_id}"
                )

        return {"status": "completed"}

    except Exception as e:
        logger.error(f"Market scan failed: {e}")
        return {"status": "failed", "error": str(e)}


async def daily_light_scan(ctx: dict[str, Any]) -> dict[str, str]:
    """Run daily post-market-close light scan for all configured indices.

    Called by arq cron at 09:30 UTC (17:30 CST) on weekdays.
    Delegates to run_market_scan with scan_type="daily".

    Args:
        ctx: arq worker context dict (passed through to run_market_scan).

    Returns:
        Dict with "status" key from run_market_scan.
    """
    return await run_market_scan(ctx, scan_type="daily")


async def weekly_deep_scan(ctx: dict[str, Any]) -> dict[str, str]:
    """Run weekly deep scan for all configured indices.

    Called by arq cron on Saturday at 02:00 UTC (10:00 CST).
    Delegates to run_market_scan with scan_type="weekly".

    Args:
        ctx: arq worker context dict (passed through to run_market_scan).

    Returns:
        Dict with "status" key from run_market_scan.
    """
    return await run_market_scan(ctx, scan_type="weekly")


class ScannerWorkerSettings:
    """Arq worker settings for market scanner cron jobs.

    Configures:
    - 1 job function: run_market_scan (for manual enqueue via arq_pool)
    - 2 cron jobs:
        - daily_light_scan: 09:30 UTC (17:30 CST) on weekdays, 30-min timeout
        - weekly_deep_scan: Saturday 02:00 UTC (10:00 CST), 60-min timeout
    - Redis connection settings

    No on_startup/on_shutdown needed: ScanOrchestrator and its dependencies
    are created per-invocation to ensure fresh database sessions.

    Usage::

        arq stockvaluefinder.market_scanner.worker.ScannerWorkerSettings
    """

    functions = [run_market_scan]
    cron_jobs = [
        cron(
            daily_light_scan,
            hour=9,
            minute=30,
            weekday={0, 1, 2, 3, 4},
            unique=True,
            max_tries=1,
            timeout=1800,
        ),
        cron(
            weekly_deep_scan,
            weekday={5},
            hour=2,
            minute=0,
            unique=True,
            max_tries=1,
            timeout=3600,
        ),
    ]
    redis_settings = get_arq_redis_settings()


__all__ = [
    "ScannerWorkerSettings",
    "daily_light_scan",
    "run_market_scan",
    "weekly_deep_scan",
]
