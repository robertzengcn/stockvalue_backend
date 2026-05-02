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

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
from arq import cron
from arq.connections import RedisSettings

from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.db.models.pending_disclosure import PendingDisclosureDB
from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository
from stockvaluefinder.pipeline.repo import PipelineTaskRepository
from stockvaluefinder.pipeline.state import PipelineState
from stockvaluefinder.pipeline.watcher import WatcherService
from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)

config = PipelineConfig()


# ---------------------------------------------------------------------------
# Helper functions for download_report
# ---------------------------------------------------------------------------


def _extract_pdf_url(source_raw: dict[str, Any] | None) -> str | None:
    """Extract PDF download URL from CNInfo disclosure metadata.

    The CNInfo detail URL contains announcementId as a query parameter.
    PDF download URL pattern: https://static.cninfo.com.cn/{announcementId}.PDF

    Args:
        source_raw: Raw disclosure metadata dict from pending_disclosures.

    Returns:
        PDF download URL string, or None if URL cannot be constructed.
    """
    if source_raw is None:
        return None

    detail_url = source_raw.get("公告链接", "")
    if not detail_url:
        return None

    parsed = urlparse(detail_url)
    params = parse_qs(parsed.query)
    announcement_id = params.get("announcementId", [None])[0]

    if announcement_id:
        return f"https://static.cninfo.com.cn/{announcement_id}.PDF"
    return None


async def _download_pdf(
    client: httpx.AsyncClient, url: str, delay: float
) -> tuple[bytes, str]:
    """Download PDF via streaming, compute SHA256 hash.

    Applies rate limiting by sleeping for the configured delay before
    the request. Validates Content-Type is PDF or octet-stream to
    reject HTML error pages.

    Args:
        client: Async HTTP client for streaming download.
        url: URL to download the PDF from.
        delay: Seconds to sleep before request (rate limiting).

    Returns:
        Tuple of (pdf_bytes, sha256_hex_digest).

    Raises:
        ExternalAPIError: If Content-Type is not PDF or octet-stream.
    """
    await asyncio.sleep(delay)

    async with client.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            raise ExternalAPIError(
                f"Expected PDF, got {content_type}",
                service="cninfo",
                status_code=response.status_code,
            )

        chunks: list[bytes] = []
        hasher = hashlib.sha256()

        async for chunk in response.aiter_bytes(chunk_size=8192):
            chunks.append(chunk)
            hasher.update(chunk)

        pdf_bytes = b"".join(chunks)
        return pdf_bytes, hasher.hexdigest()


async def _get_source_metadata(
    session: Any, task: Any
) -> tuple[str | None, dict[str, Any] | None]:
    """Query pending_disclosures for source metadata.

    Parses the task's business_key to extract ticker, fiscal_year, and
    report_type, then queries for a matching disclosure record.

    Args:
        session: Async database session.
        task: PipelineTaskDB with business_key field.

    Returns:
        Tuple of (source_id from announcement URL, source_raw dict).
    """
    from sqlalchemy import select

    parts = task.business_key.split(":")
    if len(parts) < 3:
        return None, None

    ticker, fiscal_year_str, report_type = parts[0], parts[1], parts[2]

    try:
        fiscal_year = int(fiscal_year_str)
    except ValueError:
        return None, None

    stmt = (
        select(PendingDisclosureDB)
        .where(
            PendingDisclosureDB.ticker == ticker,
            PendingDisclosureDB.fiscal_year == fiscal_year,
            PendingDisclosureDB.report_type == report_type,
        )
        .order_by(PendingDisclosureDB.created_at.desc())
    )
    result = await session.execute(stmt)
    disclosure = result.scalars().first()

    if disclosure is None:
        return None, None

    # Extract source_id from the announcement URL in source_raw
    source_raw = disclosure.source_raw
    source_id = None
    if source_raw:
        detail_url = source_raw.get("公告链接", "")
        if detail_url:
            parsed = urlparse(detail_url)
            params = parse_qs(parsed.query)
            source_id = params.get("announcementId", [None])[0]

    return source_id, source_raw


async def _enqueue_parse(task_id: str) -> None:
    """Enqueue parse_report job for the given task.

    Creates a temporary Redis connection to enqueue the job with
    per-task uniqueness via _job_id.

    Args:
        task_id: UUID of the pipeline task to parse.
    """
    from arq import create_pool as arq_create_pool

    pool = await arq_create_pool(RedisSettings(database=config.redis_db))
    try:
        await pool.enqueue_job("parse_report", task_id, _job_id=f"parse:{task_id}")
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# Worker lifecycle hooks
# ---------------------------------------------------------------------------


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
    """Download a financial report PDF from CNInfo.

    Retrieves the task from the database, transitions to DOWNLOADING,
    extracts the PDF URL from disclosure metadata, streams the PDF via
    httpx, computes SHA256, stores to filesystem, creates a document
    record, transitions to PARSING, and enqueues the parse job.

    On any exception, transitions the task to FAILED and re-raises
    so arq can apply its retry policy.

    Args:
        ctx: Worker context dict with http_client and session_factory.
        task_id: UUID of the pipeline task to process.
    """
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        repo = PipelineTaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return

        # Transition to DOWNLOADING
        await repo.transition_state(
            task_id, PipelineState.DOWNLOADING, current_stage="downloading"
        )

        try:
            # Get source metadata from pending_disclosures
            source_id, source_raw = await _get_source_metadata(session, task)

            # Extract PDF URL from source_raw
            pdf_url = _extract_pdf_url(source_raw)

            if pdf_url is None:
                raise ExternalAPIError(
                    "Cannot construct PDF URL from disclosure metadata",
                    service="cninfo",
                )

            # Check dedup by source_id before downloading
            doc_repo = PipelineDocumentRepository(session)
            if source_id:
                existing = await doc_repo.get_by_source_id(source_id)
                if existing is not None:
                    logger.warning(
                        f"Document with source_id={source_id} already exists, skipping download"
                    )
                    await repo.transition_state(
                        task_id, PipelineState.PARSING, current_stage="parsing"
                    )
                    await session.commit()
                    await _enqueue_parse(task_id)
                    return

            # Download PDF with rate limiting
            http_client: httpx.AsyncClient = ctx["http_client"]
            pdf_bytes, content_hash = await _download_pdf(
                http_client, pdf_url, config.request_delay_seconds
            )

            # Check dedup by content hash
            existing_hash = await doc_repo.get_by_content_hash(content_hash)
            if existing_hash is not None:
                logger.warning(
                    f"Document with content_hash={content_hash[:16]}... already exists, skipping write"
                )
                await repo.transition_state(
                    task_id, PipelineState.PARSING, current_stage="parsing"
                )
                await session.commit()
                await _enqueue_parse(task_id)
                return

            # Build file path per D-02: UPLOAD_DIR/{ticker}/{fy}/{type}/{source_id}.pdf
            parts = task.business_key.split(":")
            ticker = parts[0] if len(parts) >= 1 else "unknown"
            fiscal_year = parts[1] if len(parts) >= 2 else "0000"
            report_type = parts[2] if len(parts) >= 3 else "unknown"
            file_name = f"{source_id or content_hash[:16]}.pdf"
            file_path = (
                Path(rag_config.UPLOAD_DIR)
                / ticker
                / fiscal_year
                / report_type
                / file_name
            )

            # Create directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write PDF bytes
            file_path.write_bytes(pdf_bytes)

            # Create document record
            await doc_repo.create_document(
                task_id=task_id,
                source_url=pdf_url,
                source_id=source_id,
                content_hash=content_hash,
                file_path=str(file_path),
                file_size=len(pdf_bytes),
            )

            # Transition to PARSING
            await repo.transition_state(
                task_id, PipelineState.PARSING, current_stage="parsing"
            )
            await session.commit()

            # Enqueue parse_report
            await _enqueue_parse(task_id)

            logger.info(
                f"Downloaded PDF for task {task_id}: {len(pdf_bytes)} bytes, hash={content_hash[:16]}..."
            )

        except Exception as e:
            logger.error(
                f"download_report failed for task {task_id}: {e}", exc_info=True
            )
            await repo.transition_state(
                task_id, PipelineState.FAILED, error_message=str(e)
            )
            await session.commit()
            raise


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
