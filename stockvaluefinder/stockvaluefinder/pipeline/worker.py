"""Arq worker process for the pipeline.

Defines the WorkerSettings class that configures an arq worker with:
- 3 stub job functions: download_report, parse_report, analyze_report
- 1 watcher job function: process_disclosures
- 2 cron jobs: reap_stuck_tasks (every N minutes), watch_disclosures (daily 09:00)
- on_startup/on_shutdown hooks for resource management

The worker runs as a separate process alongside FastAPI. It connects to
Redis for job queue management and PostgreSQL for state persistence.

Usage:
    arq stockvaluefinder.pipeline.worker.WorkerSettings
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from arq import cron
from arq.connections import RedisSettings

from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.repo import PipelineTaskRepository
from stockvaluefinder.pipeline.watcher import WatcherService

logger = logging.getLogger(__name__)

config = PipelineConfig()


async def on_startup(ctx: dict[str, Any]) -> None:
    """Initialize worker resources.

    Creates shared httpx client, session factory, and WatcherService
    for job functions to access via ctx dict.

    Args:
        ctx: Worker context dict, shared across all job invocations.
    """
    ctx["http_client"] = httpx.AsyncClient(timeout=config.job_timeout_seconds)
    ctx["session_factory"] = async_session_maker

    akshare_client = AKShareClient()
    ctx["watcher"] = WatcherService(
        akshare_client=akshare_client,
        session_factory=ctx["session_factory"],
        config=config,
    )

    logger.info("Pipeline worker started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Clean up worker resources.

    Closes the shared httpx client.

    Args:
        ctx: Worker context dict.
    """
    client: httpx.AsyncClient = ctx["http_client"]
    await client.aclose()
    logger.info("Pipeline worker shut down")


async def download_report(ctx: dict[str, Any], task_id: str) -> None:
    """Stub: Download a financial report PDF.

    Actual implementation deferred to Phase 7.

    Args:
        ctx: Worker context dict with http_client and session_factory.
        task_id: UUID of the pipeline task to process.
    """
    logger.info(f"download_report called for task_id={task_id} (stub)")


async def parse_report(ctx: dict[str, Any], task_id: str) -> None:
    """Stub: Parse a downloaded financial report.

    Actual implementation deferred to Phase 7.

    Args:
        ctx: Worker context dict with http_client and session_factory.
        task_id: UUID of the pipeline task to process.
    """
    logger.info(f"parse_report called for task_id={task_id} (stub)")


async def analyze_report(ctx: dict[str, Any], task_id: str) -> None:
    """Stub: Analyze a parsed financial report.

    Actual implementation deferred to Phase 7.

    Args:
        ctx: Worker context dict with http_client and session_factory.
        task_id: UUID of the pipeline task to process.
    """
    logger.info(f"analyze_report called for task_id={task_id} (stub)")


async def watch_disclosures(ctx: dict[str, Any]) -> None:
    """Cron function: poll for newly disclosed financial reports.

    Runs daily at 09:00 CST. During off-season (months not in
    high_season_months), only polls on Mondays (D-07, D-08).

    This function never raises -- errors are caught and logged to
    prevent the cron from crashing.

    Args:
        ctx: Worker context dict with watcher and config.
    """
    now = datetime.now(timezone.utc)

    # Season check: skip if off-season and not Monday
    if now.month not in config.high_season_months and now.weekday() != 0:
        logger.debug(
            "Off-season and not Monday, skipping poll",
            extra={"month": now.month, "weekday": now.weekday()},
        )
        return

    watcher = ctx.get("watcher")
    if watcher is None:
        logger.error("No watcher in worker context")
        return

    try:
        result = await watcher.poll_disclosures()
        logger.info(
            "Poll complete",
            extra={
                "staged_count": result.staged_count,
                "akshare_success": result.akshare_success,
                "cninfo_fallback": result.cninfo_fallback,
            },
        )
    except Exception as e:
        logger.error(f"watch_disclosures poll failed: {e}", exc_info=True)


async def process_disclosures(ctx: dict[str, Any], poll_id: str) -> None:
    """Job function: process staged disclosures for a poll cycle.

    Reads unprocessed disclosures from the staging table, detects
    new vs. amended reports, and enqueues download jobs.

    Catches and logs exceptions without re-raising to prevent
    arq retry loops on logic errors.

    Args:
        ctx: Worker context dict with watcher.
        poll_id: UUID of the poll cycle to process.
    """
    watcher = ctx.get("watcher")
    if watcher is None:
        logger.error("No watcher in worker context")
        return

    try:
        result = await watcher.process_disclosures(poll_id)
        logger.info(
            "Processed disclosures",
            extra={
                "poll_id": poll_id,
                "new_count": result.new_count,
                "amendment_count": result.amendment_count,
                "skip_count": result.skip_count,
            },
        )
    except Exception as e:
        logger.error(
            f"process_disclosures failed for poll {poll_id}: {e}", exc_info=True
        )


async def reap_stuck_tasks(ctx: dict[str, Any]) -> None:
    """Cron function: scan for and reset stuck pipeline tasks.

    Queries for tasks in DOWNLOADING/PARSING/ANALYZING states that
    haven't been updated within the configured timeout. Resets them
    to PENDING (with retry increment) or FAILED (if max retries exceeded).

    This function never raises -- errors are caught and logged to
    prevent the cron from crashing.

    Args:
        ctx: Worker context dict with session_factory.
    """
    session_factory = ctx.get("session_factory")
    if session_factory is None:
        logger.error("No session_factory in worker context, skipping reap")
        return

    try:
        async with session_factory() as session:
            repo = PipelineTaskRepository(session)
            stuck_tasks = await repo.get_stuck_tasks(config.stuck_timeout_minutes)

            if not stuck_tasks:
                logger.debug("No stuck tasks found")
                return

            reaped_count = 0
            for task in stuck_tasks:
                try:
                    result = await repo.reset_task(str(task.task_id))
                    if result is not None:
                        reaped_count += 1
                except Exception as e:
                    logger.error(
                        f"Error resetting stuck task {task.task_id}: {e}",
                        exc_info=True,
                    )

            await session.commit()
            logger.info(
                f"Reaped {reaped_count} stuck tasks out of {len(stuck_tasks)} found"
            )

    except Exception as e:
        logger.error(f"Error in reap_stuck_tasks: {e}", exc_info=True)


class WorkerSettings:
    """Arq worker settings for the pipeline.

    Configures:
    - 3 stub job functions + process_disclosures watcher job
    - 2 cron jobs: reap_stuck_tasks + watch_disclosures
    - Startup/shutdown lifecycle hooks
    - Redis connection settings
    """

    functions = [
        download_report,
        parse_report,
        analyze_report,
        process_disclosures,
    ]
    cron_jobs = [
        cron(
            reap_stuck_tasks,
            minute=set(range(0, 60, config.reaper_interval_minutes)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
            timeout=60,
        ),
        cron(
            watch_disclosures,
            hour=9,
            minute=0,
            run_at_startup=True,
            unique=True,
            max_tries=1,
            timeout=300,
        ),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings(database=config.redis_db)


__all__ = [
    "WorkerSettings",
    "on_startup",
    "on_shutdown",
    "download_report",
    "parse_report",
    "analyze_report",
    "process_disclosures",
    "reap_stuck_tasks",
    "watch_disclosures",
]
