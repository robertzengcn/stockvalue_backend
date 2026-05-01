"""Arq worker process for the pipeline.

Defines the WorkerSettings class that configures an arq worker with:
- 3 stub job functions: download_report, parse_report, analyze_report
- 1 cron job: reap_stuck_tasks (runs every N minutes per config)
- on_startup/on_shutdown hooks for resource management

The worker runs as a separate process alongside FastAPI. It connects to
Redis for job queue management and PostgreSQL for state persistence.

Usage:
    arq stockvaluefinder.pipeline.worker.WorkerSettings
"""

import logging
from typing import Any

import httpx
from arq import cron
from arq.connections import RedisSettings

from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.repo import PipelineTaskRepository

logger = logging.getLogger(__name__)

config = PipelineConfig()


async def on_startup(ctx: dict[str, Any]) -> None:
    """Initialize worker resources.

    Creates shared httpx client and stores session factory for
    job functions to access via ctx dict.

    Args:
        ctx: Worker context dict, shared across all job invocations.
    """
    ctx["http_client"] = httpx.AsyncClient(timeout=config.job_timeout_seconds)
    ctx["session_factory"] = async_session_maker
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
    - 3 stub job functions with retry and timeout settings
    - 1 cron job for reaping stuck tasks
    - Startup/shutdown lifecycle hooks
    - Redis connection settings
    """

    functions = [
        download_report,
        parse_report,
        analyze_report,
    ]
    cron_jobs = [
        cron(
            reap_stuck_tasks,
            minute=set(range(0, 60, config.reaper_interval_minutes)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
            timeout=60,
        )
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
    "reap_stuck_tasks",
]
