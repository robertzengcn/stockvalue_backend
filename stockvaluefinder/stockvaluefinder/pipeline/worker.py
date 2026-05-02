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
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

import httpx
from arq import cron
from arq.connections import RedisSettings

from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.db.models.pending_disclosure import PendingDisclosureDB
from stockvaluefinder.external.akshare_client import AKShareClient
from stockvaluefinder.models.enums import Market
from stockvaluefinder.models.valuation import DCFParams
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.document_repo import PipelineDocumentRepository
from stockvaluefinder.pipeline.repo import PipelineTaskRepository
from stockvaluefinder.pipeline.state import PipelineState
from stockvaluefinder.pipeline.watcher import WatcherService
from stockvaluefinder.services.document_service import DocumentService
from stockvaluefinder.services.risk_service import RiskAnalyzer
from stockvaluefinder.services.valuation_service import DCFValuationService
from stockvaluefinder.services.yield_service import YieldAnalyzer
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


async def _enqueue_analyze(task_id: str, business_key: str) -> None:
    """Enqueue analyze_report job for the given task.

    Creates a temporary Redis connection to enqueue the job with
    per-ticker uniqueness via _job_id.

    Args:
        task_id: UUID of the pipeline task to analyze.
        business_key: Business key (ticker:fiscal_year:report_type) for uniqueness.
    """
    from arq import create_pool as arq_create_pool

    pool = await arq_create_pool(RedisSettings(database=config.redis_db))
    try:
        await pool.enqueue_job(
            "analyze_report", task_id, _job_id=f"analyze:{business_key}"
        )
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# Helper functions for analyze_report
# ---------------------------------------------------------------------------


def _map_akshare_to_report(
    income: dict[str, Any],
    balance: dict[str, Any],
    cashflow: dict[str, Any],
    ticker: str,
    fiscal_year: int,
) -> dict[str, Any]:
    """Map AKShare column names to analyzer input fields.

    Copies the field mapping pattern from data_service._get_financial_report_from_akshare.
    Maps English column names from AKShare stock_*_by_report_em APIs to the
    standardized field names expected by RiskAnalyzer, DCFValuationService, and
    YieldAnalyzer.

    All numeric values are converted to str() to match analyzer expectations
    (analyzers use Decimal(str(value)) internally).

    Args:
        income: Income statement dict from AKShare get_profit_sheet()[0].
        balance: Balance sheet dict from AKShare get_balance_sheet()[0].
        cashflow: Cash flow dict from AKShare get_cash_flow_sheet()[0].
        ticker: Stock ticker (e.g., '600519.SH').
        fiscal_year: Fiscal year of the report.

    Returns:
        Standardized financial report dict for analyzer consumption.
    """
    # Compute gross margin from income data
    revenue = float(income.get("TOTAL_OPERATE_INCOME", 0))
    cost = float(income.get("OPERATE_COST", 0))
    gross_margin = (revenue - cost) / revenue if revenue > 0 else 0.0

    return {
        "ticker": ticker,
        "report_id": uuid4(),
        "fiscal_year": fiscal_year,
        # Income statement
        "revenue": str(income.get("TOTAL_OPERATE_INCOME", 0)),
        "net_income": str(income.get("NETPROFIT", 0)),
        "cost_of_goods": str(income.get("OPERATE_COST", 0)),
        "sga_expense": str(income.get("TOTAL_OPERATE_COST", 0)),
        # Balance sheet (provide both naming conventions)
        "assets_total": str(balance.get("TOTAL_ASSETS", 0)),
        "total_assets": str(balance.get("TOTAL_ASSETS", 0)),
        "total_current_assets": str(balance.get("TOTAL_CURRENT_ASSETS", 0)),
        "accounts_receivable": str(balance.get("ACCOUNTS_RECE", 0)),
        "ppe": str(balance.get("FIXED_ASSET", 0)),
        "fixed_assets": str(balance.get("FIXED_ASSET", 0)),
        "total_liabilities": str(balance.get("TOTAL_LIABILITIES", 0)),
        "liabilities_total": str(balance.get("TOTAL_LIABILITIES", 0)),
        "equity_total": str(balance.get("TOTAL_EQUITY", 0)),
        "cash_and_equivalents": str(balance.get("MONETARYFUNDS", 0)),
        "goodwill": str(balance.get("GOODWILL", 0)),
        "inventory": str(balance.get("INVENTORY", 0)),
        "interest_bearing_debt": str(balance.get("TOTAL_LIABILITIES", 0)),
        "long_term_debt": str(balance.get("LONG_LOAN", 0)),
        # Cash flow
        "operating_cash_flow": str(cashflow.get("NETCASH_OPERATE", 0)),
        # Computed
        "gross_margin": gross_margin,
        "report_source": "AKShare",
    }


async def _fetch_financial_data(
    akshare: AKShareClient, ticker: str, fiscal_year: int
) -> dict[str, Any] | None:
    """Fetch structured financial data from AKShare for a given year.

    Calls get_profit_sheet, get_balance_sheet, and get_cash_flow_sheet
    for the specified fiscal year. If AKShare returns empty data, falls
    back to RAG extraction per D-07.

    Args:
        akshare: AKShareClient instance for data fetching.
        ticker: Stock ticker (e.g., '600519.SH').
        fiscal_year: Fiscal year to fetch.

    Returns:
        Standardized financial report dict, or None if data unavailable.
    """
    period = f"{fiscal_year}1231"

    try:
        income_data = await akshare.get_profit_sheet(ticker, period)
        balance_data = await akshare.get_balance_sheet(ticker, period)
        cashflow_data = await akshare.get_cash_flow_sheet(ticker, period)

        if income_data and balance_data and cashflow_data:
            return _map_akshare_to_report(
                income_data[0], balance_data[0], cashflow_data[0], ticker, fiscal_year
            )
    except Exception as e:
        logger.warning(
            f"AKShare error for {ticker} {fiscal_year}: {e}",
            exc_info=True,
        )

    # D-07: RAG fallback when AKShare fails or returns empty
    logger.warning(
        f"AKShare data unavailable for {ticker} {fiscal_year}, attempting RAG fallback"
    )
    rag_result = _extract_from_rag(ticker, fiscal_year)
    return rag_result


def _extract_from_rag(ticker: str, fiscal_year: int) -> dict[str, Any] | None:
    """Extract financial data from indexed PDF chunks via RAG.

    Queries Qdrant vector store for already-indexed PDF chunks matching
    the given ticker and fiscal_year, then uses keyword matching on chunk
    text to extract key financial metrics.

    This is a best-effort extraction -- not as reliable as AKShare structured
    data. Returns None if insufficient data found.

    Args:
        ticker: Stock ticker (e.g., '600519.SH').
        fiscal_year: Fiscal year to extract data for.

    Returns:
        Extracted financial report dict, or None if insufficient data.
    """
    try:
        from stockvaluefinder.rag.vector_store import QdrantVectorStore

        vector_store = QdrantVectorStore()
        # Use scroll to retrieve chunks by metadata filter (no query vector needed)
        qdrant_filter = vector_store._build_filter(
            {"ticker": ticker, "year": fiscal_year}
        )
        response = vector_store.client.scroll(
            collection_name=vector_store.collection,
            scroll_filter=qdrant_filter,
            limit=20,
        )
        results = response[0]  # scroll returns (points, next_offset)

        if not results:
            return None

        # Keyword-based extraction from chunk text
        extracted: dict[str, Any] = {
            "ticker": ticker,
            "report_id": uuid4(),
            "fiscal_year": fiscal_year,
            "report_source": "RAG",
        }

        # Join all chunk text for pattern matching
        all_text = " ".join((point.payload or {}).get("text", "") for point in results)

        # Extract key metrics via regex patterns
        import re

        patterns = {
            "revenue": r"营[业务]总?收入[^\d]*(\d+[\d,.]*)",
            "net_income": r"净利润[^\d]*(\d+[\d,.]*)",
            "assets_total": r"资产总[计额][^\d]*(\d+[\d,.]*)",
            "total_assets": r"资产总[计额][^\d]*(\d+[\d,.]*)",
            "total_liabilities": r"负债合[计额][^\d]*(\d+[\d,.]*)",
            "operating_cash_flow": r"经营活动.*?净.*?[流额][^\d]*(\d+[\d,.]*)",
        }

        fields_found = 0
        for field, pattern in patterns.items():
            match = re.search(pattern, all_text)
            if match:
                value_str = match.group(1).replace(",", "")
                extracted[field] = value_str
                fields_found += 1

        # Need at least revenue and total_assets to be useful
        if fields_found < 2 or "revenue" not in extracted:
            return None

        return extracted

    except Exception as e:
        logger.warning(
            f"RAG fallback failed for {ticker} {fiscal_year}: {e}",
            exc_info=True,
        )
        return None


def _get_default_dcf_params() -> DCFParams:
    """Get default DCF parameters for valuation analysis.

    Returns:
        DCFParams with conservative default values.
    """
    return DCFParams(
        growth_rate_stage1=0.05,
        growth_rate_stage2=0.03,
        years_stage1=5,
        years_stage2=5,
        terminal_growth=0.025,
        risk_free_rate=0.03,
        beta=1.0,
        market_risk_premium=0.06,
    )


def _determine_market(ticker: str) -> Market:
    """Determine market from ticker suffix.

    Args:
        ticker: Stock ticker (e.g., '600519.SH', '0700.HK').

    Returns:
        Market enum value.
    """
    if ticker.endswith(".HK"):
        return Market.HK_SHARE
    return Market.A_SHARE


async def _run_all_analyzers(
    current_report: dict[str, Any],
    previous_report: dict[str, Any] | None,
    ticker: str,
    fiscal_year: int,
) -> dict[str, Any]:
    """Run risk, valuation, and yield analysis in parallel.

    Per D-09: All 3 analyzers run in parallel via asyncio.gather with
    return_exceptions=True. Sync analyzers are wrapped in asyncio.to_thread()
    to prevent event loop blocking (Pitfall 2).

    Per D-05: Builds result_summary dict with per-analyzer status.

    Args:
        current_report: Current year financial data.
        previous_report: Previous year financial data (may be None).
        ticker: Stock ticker.
        fiscal_year: Current fiscal year.

    Returns:
        Summary dict with per-analyzer status and result references.
    """
    risk_analyzer = RiskAnalyzer()
    valuation_service = DCFValuationService()
    yield_analyzer = YieldAnalyzer()

    # Prepare valuation parameters
    dcf_params = _get_default_dcf_params()

    # Extract FCF proxy from current report (operating cash flow as base)
    base_fcf = float(current_report.get("operating_cash_flow", 0))
    shares_outstanding = float(current_report.get("shares_outstanding", 1_000_000))

    # Default price for valuation (0 if not available -- analyzer handles it)
    current_price = Decimal(current_report.get("current_price", "100"))

    valuation_id = uuid4()
    analysis_id = uuid4()

    # Per D-09: Run all 3 analyzers in parallel via asyncio.to_thread
    risk_coro = asyncio.to_thread(
        risk_analyzer.analyze, current_report, previous_report
    )
    valuation_coro = asyncio.to_thread(
        valuation_service.analyze,
        ticker,
        current_price,
        base_fcf,
        shares_outstanding,
        dcf_params,
        valuation_id,
    )

    market = _determine_market(ticker)
    gross_dividend_yield = float(current_report.get("gross_dividend_yield", 0.03))
    risk_free_bond = float(current_report.get("risk_free_bond_rate", 0.03))
    risk_free_deposit = float(current_report.get("risk_free_deposit_rate", 0.025))

    yield_coro = asyncio.to_thread(
        yield_analyzer.analyze,
        ticker,
        current_price,  # cost_basis = current_price (default assumption)
        current_price,
        gross_dividend_yield,
        risk_free_bond,
        risk_free_deposit,
        market,
        analysis_id,
    )

    results = await asyncio.gather(
        risk_coro,
        valuation_coro,
        yield_coro,
        return_exceptions=True,
    )

    # Per D-05: Build result_summary with per-analyzer status
    summary: dict[str, Any] = {}
    for name, result in zip(["risk", "valuation", "yield"], results):
        if isinstance(result, Exception):
            summary[name] = {"status": "failed", "error": str(result)}
        else:
            ref_id = str(
                getattr(
                    result,
                    "score_id",
                    getattr(
                        result,
                        "valuation_id",
                        getattr(result, "analysis_id", ""),
                    ),
                )
            )
            summary[name] = {"status": "success", "result_ref": ref_id}

    return summary


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
    """Parse a downloaded financial report through DocumentService.

    Reads the PDF from the filesystem path recorded in pipeline_documents,
    passes it through DocumentService.process_upload() for RAG indexing
    (chunking, embedding, Qdrant upsert), then enqueues the analysis step.

    Uses separate database sessions for pipeline operations and
    DocumentService to avoid transaction conflicts (Pitfall 3).

    On any exception, transitions the task to FAILED and re-raises
    so arq can apply its retry policy.

    Args:
        ctx: Worker context dict with session_factory.
        task_id: UUID of the pipeline task to process.
    """
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        repo = PipelineTaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return

        try:
            # Look up the document record for this task
            doc_repo = PipelineDocumentRepository(session)
            document = await doc_repo.get_by_task_id(task_id)

            if document is None:
                await repo.transition_state(
                    task_id,
                    PipelineState.FAILED,
                    error_message="No document record found for task",
                )
                await session.commit()
                return

            # Verify PDF file exists on filesystem
            file_path = document.file_path
            if file_path is None or not Path(file_path).exists():
                await repo.transition_state(
                    task_id,
                    PipelineState.FAILED,
                    error_message="PDF file not found at recorded path",
                )
                await session.commit()
                return

            # Read PDF bytes from filesystem
            pdf_bytes = Path(file_path).read_bytes()

            # Use a SEPARATE session for DocumentService (Pitfall 3)
            async with session_factory() as ds_session:
                doc_service = DocumentService(ds_session)
                result = await doc_service.process_upload(
                    document_id=str(document.document_id),
                    ticker=task.ticker,
                    file_name=Path(file_path).name,
                    file_path=file_path,
                    pdf_bytes=pdf_bytes,
                )
                await ds_session.commit()

            # Transition to ANALYZING after successful parse
            await repo.transition_state(
                task_id,
                PipelineState.ANALYZING,
                current_stage="analyzing",
            )
            await session.commit()

            # Enqueue analyze_report job
            await _enqueue_analyze(task_id, task.business_key)

            logger.info(
                f"Parsed report for task {task_id}: "
                f"{result.chunk_count} chunks from {result.page_count} pages"
            )

        except Exception as e:
            logger.error(f"parse_report failed for task {task_id}: {e}", exc_info=True)
            await repo.transition_state(
                task_id, PipelineState.FAILED, error_message=str(e)
            )
            await session.commit()
            raise


async def analyze_report(ctx: dict[str, Any], task_id: str) -> None:
    """Analyze a parsed financial report.

    Fetches 2 years of financial data (current + previous) from AKShare,
    runs all 3 analyzers (risk, valuation, yield) in parallel via
    asyncio.gather with return_exceptions=True, persists per-analyzer
    results in result_summary JSON, and transitions task state to DONE
    or FAILED per D-04.

    Args:
        ctx: Worker context dict with session_factory.
        task_id: UUID of the pipeline task to process.
    """
    session_factory = ctx["session_factory"]
    akshare_client = AKShareClient()

    async with session_factory() as session:
        repo = PipelineTaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task is None:
            logger.error(f"Task {task_id} not found")
            return

        try:
            # Parse business_key to extract ticker, fiscal_year, report_type
            parts = task.business_key.split(":")
            if len(parts) < 3:
                raise ValueError(f"Invalid business_key format: {task.business_key}")
            ticker, fiscal_year_str, _report_type = parts[0], parts[1], parts[2]
            fiscal_year = int(fiscal_year_str)

            # Per D-08: Fetch current year data
            current_report = await _fetch_financial_data(
                akshare_client, ticker, fiscal_year
            )
            if current_report is None:
                await repo.transition_state(
                    task_id,
                    PipelineState.FAILED,
                    error_message=(
                        f"Could not fetch current year financial data "
                        f"for {ticker} {fiscal_year}"
                    ),
                )
                await session.commit()
                return

            # Fetch previous year data (may be None)
            previous_report = await _fetch_financial_data(
                akshare_client, ticker, fiscal_year - 1
            )

            # Per D-09: Run all 3 analyzers in parallel
            summary = await _run_all_analyzers(
                current_report, previous_report, ticker, fiscal_year
            )

            # Store result_summary on task
            task.result_summary = summary

            # Per D-04: Determine final state
            failed_analyzers = [
                name for name, entry in summary.items() if entry["status"] == "failed"
            ]

            if not failed_analyzers:
                await repo.transition_state(
                    task_id,
                    PipelineState.DONE,
                    current_stage="done",
                )
            else:
                error_msg = f"Analyzers failed: {', '.join(failed_analyzers)}"
                await repo.transition_state(
                    task_id,
                    PipelineState.FAILED,
                    error_message=error_msg,
                )

            await session.commit()

            logger.info(
                f"analyze_report complete for task {task_id}: "
                f"{len(failed_analyzers)} failures"
            )

        except Exception as e:
            logger.error(
                f"analyze_report failed for task {task_id}: {e}",
                exc_info=True,
            )
            await repo.transition_state(
                task_id, PipelineState.FAILED, error_message=str(e)
            )
            await session.commit()
            raise


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
