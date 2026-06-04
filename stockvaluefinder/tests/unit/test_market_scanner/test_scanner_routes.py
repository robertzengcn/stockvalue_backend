"""Unit tests for scanner REST API endpoints.

Tests cover all 6 scanner endpoints:
- POST /api/v1/scanner/runs (admin-only scan trigger)
- GET /api/v1/scanner/runs (paginated run list)
- GET /api/v1/scanner/runs/latest/{index_code} (latest run for index)
- GET /api/v1/scanner/runs/{run_id}/candidates (paginated candidate list)
- GET /api/v1/scanner/candidates/{candidate_id} (candidate detail)
- POST /api/v1/scanner/candidates/{candidate_id}/watchlist (add to watchlist)

All external dependencies (DB, auth, worker) are mocked.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def mock_admin_user():
    """Return a mock admin user dict."""
    return {
        "user_id": str(uuid4()),
        "email": "admin@test.com",
        "role": "admin",
        "is_active": True,
    }


@pytest.fixture
def mock_normal_user():
    """Return a mock normal (non-admin) user dict."""
    return {
        "user_id": str(uuid4()),
        "email": "user@test.com",
        "role": "user",
        "is_active": True,
    }


@pytest.fixture
def app_client(mock_db):
    """Create a TestClient with mocked dependencies."""
    with patch("stockvaluefinder.api.scanner_routes.get_db", return_value=mock_db):
        from stockvaluefinder.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


def _make_auth_header(role: str = "admin") -> dict[str, str]:
    """Create a valid JWT auth header for testing.

    Uses the real JWT service to create a valid token that can pass
    get_current_user validation.
    """
    from stockvaluefinder.services.jwt_service import jwt_service

    user_id = str(uuid4())
    token = jwt_service.create_access_token(user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


def _make_run_orm(
    run_id=None,
    index_codes=None,
    scan_type="daily",
    status="completed",
    rules_version="v1",
    total_count=300,
    screened_count=50,
    candidate_count=10,
):
    """Create a mock MarketScanRunDB ORM object."""
    run_id = run_id or uuid4()
    run = MagicMock()
    run.run_id = run_id
    run.index_codes = index_codes or ["CSI300"]
    run.scan_type = scan_type
    run.status = status
    run.rules_version = rules_version
    run.total_count = total_count
    run.screened_count = screened_count
    run.candidate_count = candidate_count
    run.error_summary = None
    run.started_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    run.completed_at = datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc)
    run.created_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    run.updated_at = datetime(2026, 6, 1, 10, 30, 0, tzinfo=timezone.utc)
    return run


def _make_candidate_orm(
    candidate_id=None,
    run_id=None,
    ticker="600519.SH",
    index_code="CSI300",
    composite_score=85.5,
    snapshot=None,
):
    """Create a mock MarketScanCandidateDB ORM object."""
    candidate_id = candidate_id or uuid4()
    run_id = run_id or uuid4()
    snapshot = snapshot or {
        "margin_of_safety": 0.45,
        "intrinsic_value": 2200.0,
        "risk_level": "LOW",
    }
    candidate = MagicMock()
    candidate.candidate_id = candidate_id
    candidate.run_id = run_id
    candidate.ticker = ticker
    candidate.index_code = index_code
    candidate.composite_score = composite_score
    candidate.screening_snapshot = snapshot
    candidate.created_at = datetime(2026, 6, 1, 10, 15, 0, tzinfo=timezone.utc)
    return candidate


# ---------------------------------------------------------------------------
# Test: POST /api/v1/scanner/runs (Trigger Manual Scan)
# ---------------------------------------------------------------------------


class TestTriggerManualScan:
    """Tests for POST /api/v1/scanner/runs endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_manual_scan_success(self):
        """Test 1: POST /runs (admin) enqueues arq job and returns job_id."""
        from stockvaluefinder.api.scanner_routes import trigger_manual_scan
        from stockvaluefinder.api.scanner_routes import ManualScanRequest

        # Mock arq pool
        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"

        mock_request = MagicMock()
        mock_app = MagicMock()
        mock_app.state.arq_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_request.app = mock_app

        result = await trigger_manual_scan(
            request=ManualScanRequest(),
            req=mock_request,
            admin={"user_id": "admin", "role": "admin"},
        )

        assert result.success is True
        assert result.data["job_id"] == "test-job-123"
        assert result.data["status"] == "queued"
        mock_app.state.arq_pool.enqueue_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_requires_admin(self):
        """Test 2: POST /runs without admin role returns 403.

        This test verifies the require_admin dependency rejects non-admin
        users at the dependency level, so the endpoint itself is never called.
        """
        from stockvaluefinder.api.dependencies import require_admin

        with pytest.raises(Exception):
            # require_admin raises HTTPException(403) for non-admin users
            await require_admin(
                current_user={"user_id": "user1", "role": "user", "is_active": True}
            )

    @pytest.mark.asyncio
    async def test_trigger_no_arq_pool(self):
        """Test 3: POST /runs when arq_pool is None returns error."""
        from stockvaluefinder.api.scanner_routes import trigger_manual_scan
        from stockvaluefinder.api.scanner_routes import ManualScanRequest

        mock_request = MagicMock()
        mock_app = MagicMock()
        mock_app.state.arq_pool = None
        mock_request.app = mock_app

        result = await trigger_manual_scan(
            request=ManualScanRequest(),
            req=mock_request,
            admin={"user_id": "admin", "role": "admin"},
        )

        assert result.success is False
        assert result.error is not None
        assert "Worker" in result.error or "not available" in result.error

    @pytest.mark.asyncio
    async def test_trigger_enqueue_returns_none(self):
        """Test: POST /runs when enqueue_job returns None (duplicate)."""
        from stockvaluefinder.api.scanner_routes import trigger_manual_scan
        from stockvaluefinder.api.scanner_routes import ManualScanRequest

        mock_request = MagicMock()
        mock_app = MagicMock()
        mock_app.state.arq_pool.enqueue_job = AsyncMock(return_value=None)
        mock_request.app = mock_app

        result = await trigger_manual_scan(
            request=ManualScanRequest(),
            req=mock_request,
            admin={"user_id": "admin", "role": "admin"},
        )

        assert result.success is False
        assert (
            "already queued" in result.error.lower() or "failed" in result.error.lower()
        )

    @pytest.mark.asyncio
    async def test_trigger_with_custom_params(self):
        """Test: POST /runs with custom index_codes and scan_type."""
        from stockvaluefinder.api.scanner_routes import trigger_manual_scan
        from stockvaluefinder.api.scanner_routes import ManualScanRequest

        mock_job = MagicMock()
        mock_job.job_id = "custom-job-456"

        mock_request = MagicMock()
        mock_app = MagicMock()
        mock_app.state.arq_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_request.app = mock_app

        result = await trigger_manual_scan(
            request=ManualScanRequest(
                index_codes=["CSI500"],
                scan_type="weekly",
                top_n=50,
            ),
            req=mock_request,
            admin={"user_id": "admin", "role": "admin"},
        )

        assert result.success is True
        # Verify enqueue was called with custom params
        call_args = mock_app.state.arq_pool.enqueue_job.call_args
        assert call_args[0][0] == "run_market_scan"
        assert call_args[1]["index_codes"] == ["CSI500"]
        assert call_args[1]["scan_type"] == "weekly"
        assert call_args[1]["top_n"] == 50


# ---------------------------------------------------------------------------
# Test: GET /api/v1/scanner/runs (List Scan Runs)
# ---------------------------------------------------------------------------


class TestListScanRuns:
    """Tests for GET /api/v1/scanner/runs endpoint."""

    @pytest.mark.asyncio
    async def test_list_runs_paginated(self):
        """Test 4: GET /runs returns paginated list of runs."""
        from stockvaluefinder.api.scanner_routes import list_scan_runs

        mock_db = AsyncMock()
        run1 = _make_run_orm(run_id=uuid4())
        run2 = _make_run_orm(run_id=uuid4())

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_runs_paginated = AsyncMock(return_value=([run1, run2], 2))

            result = await list_scan_runs(
                page=1,
                limit=20,
                status=None,
                scan_type=None,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert result.data is not None
        assert len(result.data.runs) == 2
        assert result.data.pagination.total == 2
        assert result.data.pagination.page == 1
        assert result.data.pagination.limit == 20

    @pytest.mark.asyncio
    async def test_list_runs_filter_by_status(self):
        """Test 5: GET /runs filters by status query param."""
        from stockvaluefinder.api.scanner_routes import list_scan_runs

        mock_db = AsyncMock()
        run1 = _make_run_orm(run_id=uuid4(), status="completed")

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_runs_paginated = AsyncMock(return_value=([run1], 1))

            result = await list_scan_runs(
                page=1,
                limit=20,
                status="completed",
                scan_type=None,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert len(result.data.runs) == 1
        # Verify the repository was called with the status filter
        mock_repo.list_runs_paginated.assert_called_once_with(
            page=1, limit=20, status="completed", scan_type=None
        )

    @pytest.mark.asyncio
    async def test_list_runs_empty(self):
        """Test: GET /runs with no runs returns empty list."""
        from stockvaluefinder.api.scanner_routes import list_scan_runs

        mock_db = AsyncMock()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_runs_paginated = AsyncMock(return_value=([], 0))

            result = await list_scan_runs(
                page=1,
                limit=20,
                status=None,
                scan_type=None,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert len(result.data.runs) == 0
        assert result.data.pagination.total == 0


# ---------------------------------------------------------------------------
# Test: GET /api/v1/scanner/runs/latest/{index_code}
# ---------------------------------------------------------------------------


class TestGetLatestRun:
    """Tests for GET /api/v1/scanner/runs/latest/{index_code} endpoint."""

    @pytest.mark.asyncio
    async def test_get_latest_run_found(self):
        """Test 13: GET /runs/latest/{index_code} returns latest run for index."""
        from stockvaluefinder.api.scanner_routes import get_latest_run

        mock_db = AsyncMock()
        run = _make_run_orm(index_codes=["CSI300"])

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_run = AsyncMock(return_value=run)

            result = await get_latest_run(
                index_code="CSI300",
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert result.data.run_id == run.run_id
        assert result.data.index_codes == ["CSI300"]
        mock_repo.get_latest_run.assert_called_once_with("CSI300")

    @pytest.mark.asyncio
    async def test_get_latest_run_not_found(self):
        """Test: GET /runs/latest/{index_code} returns 404 if no run exists."""
        from stockvaluefinder.api.scanner_routes import get_latest_run

        mock_db = AsyncMock()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_run = AsyncMock(return_value=None)

            with pytest.raises(Exception) as exc_info:
                await get_latest_run(
                    index_code="CSI300",
                    db=mock_db,
                    current_user={"user_id": "user1", "role": "user"},
                )

            # Should be HTTPException with 404
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test: GET /api/v1/scanner/runs/{run_id}/candidates
# ---------------------------------------------------------------------------


class TestListCandidates:
    """Tests for GET /api/v1/scanner/runs/{run_id}/candidates endpoint."""

    @pytest.mark.asyncio
    async def test_list_candidates_sorted_by_composite_score(self):
        """Test 6: GET /runs/{run_id}/candidates returns paginated candidates."""
        from stockvaluefinder.api.scanner_routes import list_candidates

        mock_db = AsyncMock()
        run_id = uuid4()
        c1 = _make_candidate_orm(run_id=run_id, composite_score=90.0)
        c2 = _make_candidate_orm(run_id=run_id, composite_score=80.0)

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanCandidateRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_candidates_paginated = AsyncMock(return_value=([c1, c2], 2))

            result = await list_candidates(
                run_id=run_id,
                page=1,
                limit=20,
                index_code=None,
                sort_by="composite_score",
                sort_order="desc",
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert len(result.data.candidates) == 2
        assert result.data.pagination.total == 2
        # Check snapshot fields are extracted
        assert result.data.candidates[0].safety_margin == 0.45
        assert result.data.candidates[0].intrinsic_value == 2200.0
        assert result.data.candidates[0].risk_level == "LOW"

    @pytest.mark.asyncio
    async def test_list_candidates_sort_by_safety_margin(self):
        """Test 7: GET /runs/{run_id}/candidates sorts by safety_margin."""
        from stockvaluefinder.api.scanner_routes import list_candidates

        mock_db = AsyncMock()
        run_id = uuid4()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanCandidateRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_candidates_paginated = AsyncMock(return_value=([], 0))

            await list_candidates(
                run_id=run_id,
                page=1,
                limit=20,
                index_code=None,
                sort_by="safety_margin",
                sort_order="desc",
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        mock_repo.list_candidates_paginated.assert_called_once_with(
            run_id=run_id,
            page=1,
            limit=20,
            index_code=None,
            sort_by="safety_margin",
            sort_order="desc",
        )

    @pytest.mark.asyncio
    async def test_list_candidates_invalid_sort(self):
        """Test: GET /runs/{run_id}/candidates with invalid sort_by returns error."""
        from stockvaluefinder.api.scanner_routes import list_candidates

        mock_db = AsyncMock()
        run_id = uuid4()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanCandidateRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_candidates_paginated = AsyncMock(
                side_effect=ValueError("Invalid sort_by 'invalid_field'")
            )

            result = await list_candidates(
                run_id=run_id,
                page=1,
                limit=20,
                index_code=None,
                sort_by="invalid_field",
                sort_order="desc",
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is False


# ---------------------------------------------------------------------------
# Test: GET /api/v1/scanner/candidates/{candidate_id}
# ---------------------------------------------------------------------------


class TestGetCandidateDetail:
    """Tests for GET /api/v1/scanner/candidates/{candidate_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_candidate_detail_found(self):
        """Test 8: GET /candidates/{id} returns full detail with screening_snapshot."""
        from stockvaluefinder.api.scanner_routes import get_candidate_detail

        mock_db = AsyncMock()
        candidate_id = uuid4()
        run_id = uuid4()
        snapshot = {
            "margin_of_safety": 0.45,
            "intrinsic_value": 2200.0,
            "risk_level": "LOW",
            "reasons": ["Strong cash flow", "Low debt"],
        }
        candidate = _make_candidate_orm(
            candidate_id=candidate_id,
            run_id=run_id,
            snapshot=snapshot,
        )

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_candidate_by_id = AsyncMock(return_value=candidate)

            result = await get_candidate_detail(
                candidate_id=candidate_id,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert result.data.candidate_id == candidate_id
        assert result.data.screening_snapshot == snapshot
        assert result.data.screening_snapshot["reasons"] == [
            "Strong cash flow",
            "Low debt",
        ]

    @pytest.mark.asyncio
    async def test_get_candidate_detail_not_found(self):
        """Test 9: GET /candidates/{id} returns 404 for unknown id."""
        from stockvaluefinder.api.scanner_routes import get_candidate_detail

        mock_db = AsyncMock()
        candidate_id = uuid4()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_candidate_by_id = AsyncMock(return_value=None)

            with pytest.raises(Exception) as exc_info:
                await get_candidate_detail(
                    candidate_id=candidate_id,
                    db=mock_db,
                    current_user={"user_id": "user1", "role": "user"},
                )

            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test: POST /api/v1/scanner/candidates/{candidate_id}/watchlist
# ---------------------------------------------------------------------------


class TestAddToWatchlist:
    """Tests for POST /api/v1/scanner/candidates/{candidate_id}/watchlist endpoint."""

    @pytest.mark.asyncio
    async def test_add_to_watchlist_new(self):
        """Test 10: POST /candidates/{id}/watchlist adds and returns already_exists=False."""
        from stockvaluefinder.api.scanner_routes import add_to_watchlist

        mock_db = AsyncMock()
        candidate_id = uuid4()
        run_id = uuid4()
        candidate = _make_candidate_orm(
            candidate_id=candidate_id,
            run_id=run_id,
            ticker="600519.SH",
        )

        with (
            patch(
                "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
            ) as MockRunRepo,
            patch(
                "stockvaluefinder.api.scanner_routes.WatchlistRepository"
            ) as MockWatchlistRepo,
        ):
            mock_run_repo = MockRunRepo.return_value
            mock_run_repo.get_candidate_by_id = AsyncMock(return_value=candidate)

            mock_watchlist_repo = MockWatchlistRepo.return_value
            mock_watchlist_repo.get_by_ticker = AsyncMock(return_value=None)
            mock_watchlist_repo.add = AsyncMock()

            result = await add_to_watchlist(
                candidate_id=candidate_id,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert result.data["ticker"] == "600519.SH"
        assert result.data["already_exists"] is False
        mock_watchlist_repo.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_watchlist_duplicate(self):
        """Test 11: POST /candidates/{id}/watchlist duplicate returns already_exists=True."""
        from stockvaluefinder.api.scanner_routes import add_to_watchlist

        mock_db = AsyncMock()
        candidate_id = uuid4()
        run_id = uuid4()
        candidate = _make_candidate_orm(
            candidate_id=candidate_id,
            run_id=run_id,
            ticker="600519.SH",
        )

        existing_watchlist = MagicMock()
        existing_watchlist.ticker = "600519.SH"

        with (
            patch(
                "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
            ) as MockRunRepo,
            patch(
                "stockvaluefinder.api.scanner_routes.WatchlistRepository"
            ) as MockWatchlistRepo,
        ):
            mock_run_repo = MockRunRepo.return_value
            mock_run_repo.get_candidate_by_id = AsyncMock(return_value=candidate)

            mock_watchlist_repo = MockWatchlistRepo.return_value
            mock_watchlist_repo.get_by_ticker = AsyncMock(
                return_value=existing_watchlist
            )

            result = await add_to_watchlist(
                candidate_id=candidate_id,
                db=mock_db,
                current_user={"user_id": "user1", "role": "user"},
            )

        assert result.success is True
        assert result.data["ticker"] == "600519.SH"
        assert result.data["already_exists"] is True
        # Should NOT call add when already exists
        mock_watchlist_repo.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_to_watchlist_candidate_not_found(self):
        """Test 12: POST /candidates/{id}/watchlist returns 404 for unknown candidate."""
        from stockvaluefinder.api.scanner_routes import add_to_watchlist

        mock_db = AsyncMock()
        candidate_id = uuid4()

        with patch(
            "stockvaluefinder.api.scanner_routes.MarketScanRunRepository"
        ) as MockRunRepo:
            mock_run_repo = MockRunRepo.return_value
            mock_run_repo.get_candidate_by_id = AsyncMock(return_value=None)

            with pytest.raises(Exception) as exc_info:
                await add_to_watchlist(
                    candidate_id=candidate_id,
                    db=mock_db,
                    current_user={"user_id": "user1", "role": "user"},
                )

            assert exc_info.value.status_code == 404
