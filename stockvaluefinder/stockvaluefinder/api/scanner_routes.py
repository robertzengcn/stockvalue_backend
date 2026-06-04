"""Scanner REST API endpoints for scan management, result queries, and watchlist integration.

Provides 6 endpoints:
- POST /runs: Admin-only scan trigger (enqueues arq job)
- GET /runs: List scan runs with pagination and filters
- GET /runs/latest/{index_code}: Get latest run for an index
- GET /runs/{run_id}/candidates: List candidates with pagination and sorting
- GET /candidates/{candidate_id}: Full candidate detail
- POST /candidates/{candidate_id}/watchlist: Add candidate to watchlist
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_current_user, require_admin
from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse, PaginationMeta
from stockvaluefinder.models.market_scanner import (
    CandidateDetailResponse,
    CandidateListItemResponse,
    CandidateListResponse,
    ScanRunListResponse,
    ScanRunResponse,
)
from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository
from stockvaluefinder.repositories.market_scan_repo import (
    MarketScanCandidateRepository,
    MarketScanRunRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class ManualScanRequest(BaseModel):
    """Request body for manual scan trigger.

    Attributes:
        index_codes: List of index pool identifiers to scan.
        scan_type: Scan frequency type (daily or weekly).
        top_n: Optional override for top N stocks.
    """

    index_codes: list[str] = Field(
        default=["CSI300", "CSI500"],
        description="Index codes to scan",
    )
    scan_type: str = Field(
        default="daily",
        description="Scan type (daily or weekly)",
    )
    top_n: int | None = Field(
        default=None,
        description="Override top N (None = use config default)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"index_codes": ["CSI300", "CSI500"], "scan_type": "daily"},
                {"index_codes": ["CSI300"], "scan_type": "weekly", "top_n": 50},
            ]
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_run_to_response(run: Any) -> ScanRunResponse:
    """Map a MarketScanRunDB ORM object to a ScanRunResponse Pydantic model.

    Args:
        run: MarketScanRunDB ORM instance.

    Returns:
        ScanRunResponse with run summary data.
    """
    return ScanRunResponse(
        run_id=run.run_id,
        index_codes=list(run.index_codes)
        if not isinstance(run.index_codes, list)
        else run.index_codes,
        scan_type=run.scan_type,
        status=run.status,
        rules_version=run.rules_version,
        total_count=run.total_count,
        screened_count=run.screened_count,
        candidate_count=run.candidate_count,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def _map_candidate_to_list_item(candidate: Any) -> CandidateListItemResponse:
    """Map a MarketScanCandidateDB ORM object to a CandidateListItemResponse.

    Extracts safety_margin, intrinsic_value, and risk_level from the
    screening_snapshot JSONB field.

    Args:
        candidate: MarketScanCandidateDB ORM instance.

    Returns:
        CandidateListItemResponse with extracted snapshot fields.
    """
    snapshot = candidate.screening_snapshot or {}
    return CandidateListItemResponse(
        candidate_id=candidate.candidate_id,
        run_id=candidate.run_id,
        ticker=candidate.ticker,
        index_code=candidate.index_code,
        composite_score=candidate.composite_score,
        safety_margin=snapshot.get("margin_of_safety"),
        intrinsic_value=snapshot.get("intrinsic_value"),
        risk_level=snapshot.get("risk_level"),
        created_at=candidate.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/runs", response_model=ApiResponse[dict])
async def trigger_manual_scan(
    request: ManualScanRequest,
    req: Request,
    admin: dict = Depends(require_admin),
) -> ApiResponse[dict]:
    """Trigger manual scan (admin only). Enqueues arq job, returns job_id.

    Validates scan_type against allowed values, then enqueues a
    run_market_scan job via the arq pool. Returns immediately with
    the job_id so the caller can poll for status.

    Args:
        request: ManualScanRequest with scan parameters.
        req: FastAPI Request object (for accessing app.state.arq_pool).
        admin: Admin user dict (injected by require_admin dependency).

    Returns:
        ApiResponse with job_id and status="queued", or error.
    """
    # Validate scan_type
    valid_scan_types = {"daily", "weekly"}
    if request.scan_type not in valid_scan_types:
        return ApiResponse(
            success=False,
            error=f"Invalid scan_type '{request.scan_type}'. "
            f"Allowed: {sorted(valid_scan_types)}",
        )

    # Get arq pool from app state
    arq_pool = getattr(req.app.state, "arq_pool", None)
    if arq_pool is None:
        return ApiResponse(
            success=False,
            error="Worker not available. Scan cannot be triggered.",
        )

    # Enqueue the job
    job = await arq_pool.enqueue_job(
        "run_market_scan",
        index_codes=request.index_codes,
        scan_type=request.scan_type,
        top_n=request.top_n,
    )

    if job is None:
        return ApiResponse(
            success=False,
            error="Scan already queued or failed to enqueue.",
        )

    logger.info(
        f"Admin {admin.get('email')} triggered {request.scan_type} scan "
        f"for {request.index_codes}, job_id={job.job_id}"
    )

    return ApiResponse(
        success=True,
        data={"job_id": job.job_id, "status": "queued"},
    )


@router.get("/runs", response_model=ApiResponse[ScanRunListResponse])
async def list_scan_runs(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    scan_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[ScanRunListResponse]:
    """List scan runs with pagination and optional filters (EXE-05).

    Args:
        page: Page number (1-based).
        limit: Items per page (capped at 100).
        status: Optional status filter.
        scan_type: Optional scan type filter.
        db: Database session.
        current_user: Authenticated user dict.

    Returns:
        ApiResponse with paginated list of ScanRunResponse objects.
    """
    capped_limit = min(limit, 100)
    run_repo = MarketScanRunRepository(db)
    runs, total = await run_repo.list_runs_paginated(
        page=page,
        limit=capped_limit,
        status=status,
        scan_type=scan_type,
    )

    run_responses = [_map_run_to_response(run) for run in runs]

    return ApiResponse(
        success=True,
        data=ScanRunListResponse(
            runs=run_responses,
            pagination=PaginationMeta(
                total=total,
                page=page,
                limit=capped_limit,
            ),
        ),
    )


@router.get("/runs/latest/{index_code}", response_model=ApiResponse[ScanRunResponse])
async def get_latest_run(
    index_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[ScanRunResponse]:
    """Get the latest scan run for a given index code (EXE-05).

    Args:
        index_code: Index pool identifier (e.g., CSI300, CSI500).
        db: Database session.
        current_user: Authenticated user dict.

    Returns:
        ApiResponse with the latest ScanRunResponse for the index.

    Raises:
        HTTPException: 404 if no run exists for the given index code.
    """
    run_repo = MarketScanRunRepository(db)
    run = await run_repo.get_latest_run(index_code)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scan run found for index {index_code}",
        )

    return ApiResponse(
        success=True,
        data=_map_run_to_response(run),
    )


@router.get(
    "/runs/{run_id}/candidates", response_model=ApiResponse[CandidateListResponse]
)
async def list_candidates(
    run_id: UUID,
    page: int = 1,
    limit: int = 20,
    index_code: str | None = None,
    sort_by: str = "composite_score",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[CandidateListResponse]:
    """List candidates for a scan run with pagination and sorting (EXE-06).

    Args:
        run_id: UUID of the scan run.
        page: Page number (1-based).
        limit: Items per page (capped at 100).
        index_code: Optional index code filter.
        sort_by: Sort field (composite_score, safety_margin, created_at).
        sort_order: Sort direction (asc or desc).
        db: Database session.
        current_user: Authenticated user dict.

    Returns:
        ApiResponse with paginated list of CandidateListItemResponse objects.
    """
    capped_limit = min(limit, 100)

    # Validate sort_order
    if sort_order not in ("asc", "desc"):
        return ApiResponse(
            success=False,
            error=f"Invalid sort_order '{sort_order}'. Allowed: asc, desc",
        )

    candidate_repo = MarketScanCandidateRepository(db)

    try:
        candidates, total = await candidate_repo.list_candidates_paginated(
            run_id=run_id,
            page=page,
            limit=capped_limit,
            index_code=index_code,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))

    candidate_responses = [_map_candidate_to_list_item(c) for c in candidates]

    return ApiResponse(
        success=True,
        data=CandidateListResponse(
            candidates=candidate_responses,
            pagination=PaginationMeta(
                total=total,
                page=page,
                limit=capped_limit,
            ),
        ),
    )


@router.get(
    "/candidates/{candidate_id}", response_model=ApiResponse[CandidateDetailResponse]
)
async def get_candidate_detail(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[CandidateDetailResponse]:
    """Get full candidate detail with screening snapshot (EXE-07).

    Args:
        candidate_id: UUID of the candidate record.
        db: Database session.
        current_user: Authenticated user dict.

    Returns:
        ApiResponse with full CandidateDetailResponse including screening_snapshot.

    Raises:
        HTTPException: 404 if candidate not found.
    """
    run_repo = MarketScanRunRepository(db)
    candidate = await run_repo.get_candidate_by_id(candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return ApiResponse(
        success=True,
        data=CandidateDetailResponse(
            candidate_id=candidate.candidate_id,
            run_id=candidate.run_id,
            ticker=candidate.ticker,
            index_code=candidate.index_code,
            composite_score=candidate.composite_score,
            screening_snapshot=candidate.screening_snapshot,
            created_at=candidate.created_at,
        ),
    )


@router.post("/candidates/{candidate_id}/watchlist", response_model=ApiResponse[dict])
async def add_to_watchlist(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Add a scan candidate to the watchlist (EXE-08).

    Looks up the candidate by ID, checks if the ticker is already in the
    watchlist, and adds it if not. Returns already_exists flag.

    Note: Uses the global watchlist (no user_id scoping). This is an accepted
    MVP limitation documented in Phase 28 research (Pitfall 3).

    Args:
        candidate_id: UUID of the candidate record.
        db: Database session.
        current_user: Authenticated user dict.

    Returns:
        ApiResponse with ticker and already_exists flag.

    Raises:
        HTTPException: 404 if candidate not found.
    """
    # Look up candidate
    run_repo = MarketScanRunRepository(db)
    candidate = await run_repo.get_candidate_by_id(candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    ticker = candidate.ticker
    snapshot = candidate.screening_snapshot or {}
    name = snapshot.get("name", ticker)

    # Check if already in watchlist
    watchlist_repo = WatchlistRepository(db)
    existing = await watchlist_repo.get_by_ticker(ticker)

    if existing is not None:
        return ApiResponse(
            success=True,
            data={"ticker": ticker, "already_exists": True},
        )

    # Add to watchlist
    await watchlist_repo.add(ticker=ticker, name=name)
    await db.commit()

    logger.info(
        f"User {current_user.get('user_id')} added {ticker} "
        f"to watchlist from candidate {candidate_id}"
    )

    return ApiResponse(
        success=True,
        data={"ticker": ticker, "already_exists": False},
    )
