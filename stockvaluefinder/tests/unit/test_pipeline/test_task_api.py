"""Unit tests for task API endpoints and supporting repo/models/config.

Tests Task 1 artifacts:
- PipelineTaskRepository.count_by_state()
- PipelineTaskRepository.list_tasks()
- PipelineConfig sandbox_enabled / sandbox_timeout fields
- Pydantic models: TriggerRequest, TaskListItemResponse, PipelineStatusResponse

Tests Task 2 artifacts:
- GET /api/v1/pipeline/status
- GET /api/v1/pipeline/tasks
- POST /api/v1/pipeline/trigger
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from stockvaluefinder.api.pipeline_routes import router as pipeline_router
from stockvaluefinder.db.base import get_db
from stockvaluefinder.db.models.pipeline_task import PipelineTaskDB


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_app() -> FastAPI:
    """Create a FastAPI app with the pipeline router for testing."""
    app = FastAPI()
    app.include_router(pipeline_router)
    return app


def _mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession for dependency override."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


GET_DB_DEPENDENCY = get_db


def _override_get_db(mock_session: AsyncMock):
    """Create a dependency override for get_db."""

    async def _get_db_override():
        yield mock_session

    return _get_db_override


def _make_pipeline_task_db(
    task_id=None,
    ticker: str = "600519.SH",
    business_key: str = "600519.SH:2023:annual",
    state: str = "pending",
    current_stage: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock PipelineTaskDB instance for testing.

    Uses MagicMock because PipelineTaskDB.__new__ does not properly
    initialize SQLAlchemy's internal attribute state, causing errors
    when accessing mapped columns outside a session context.
    """
    task = MagicMock(spec=PipelineTaskDB)
    task.task_id = task_id or uuid4()
    task.ticker = ticker
    task.business_key = business_key
    task.state = state
    task.current_stage = current_stage
    task.retry_count = 0
    task.max_retries = 3
    task.error_message = error_message
    task.result_summary = None
    task.created_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    return task


# ===================================================================
# Task 1: Repository methods + Config + Models
# ===================================================================


class TestCountByState:
    """Tests for PipelineTaskRepository.count_by_state()."""

    @pytest.mark.asyncio
    async def test_count_by_state_empty(self) -> None:
        """Test 1: count_by_state returns dict with all 6 PipelineState keys when DB is empty."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()
        # Mock execute to return empty rows
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PipelineTaskRepository(mock_session)
        result = await repo.count_by_state()

        # Assert all 6 states present with value 0
        assert set(result.keys()) == {
            "pending",
            "downloading",
            "parsing",
            "analyzing",
            "done",
            "failed",
        }
        assert all(v == 0 for v in result.values())

    @pytest.mark.asyncio
    async def test_count_by_state_with_data(self) -> None:
        """Test 2: count_by_state returns correct counts when tasks exist."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("pending", 3), ("done", 5)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PipelineTaskRepository(mock_session)
        result = await repo.count_by_state()

        assert result == {
            "pending": 3,
            "downloading": 0,
            "parsing": 0,
            "analyzing": 0,
            "done": 5,
            "failed": 0,
        }


class TestListTasks:
    """Tests for PipelineTaskRepository.list_tasks()."""

    @pytest.mark.asyncio
    async def test_list_tasks_default_pagination(self) -> None:
        """Test 3: list_tasks returns (tasks_list, total_count) with default pagination."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()

        # First call: count query; second call: data query
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[count_result, data_result])

        repo = PipelineTaskRepository(mock_session)
        tasks, total = await repo.list_tasks()

        assert tasks == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_tasks_with_state_filter(self) -> None:
        """Test 4: list_tasks filters by state."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        call_count = 0
        compiled_stmts = []

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            compiled_stmts.append(compiled)
            if call_count == 1:
                return count_result
            return data_result

        mock_session.execute = _mock_execute

        repo = PipelineTaskRepository(mock_session)
        tasks, total = await repo.list_tasks(state="pending")

        # Verify the state filter is applied in the SQL
        assert any("pending" in s for s in compiled_stmts)
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_tasks_with_ticker_filter(self) -> None:
        """Test 5: list_tasks filters by ticker."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        call_count = 0
        compiled_stmts = []

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            compiled_stmts.append(compiled)
            if call_count == 1:
                return count_result
            return data_result

        mock_session.execute = _mock_execute

        repo = PipelineTaskRepository(mock_session)
        tasks, total = await repo.list_tasks(ticker="600519.SH")

        assert any("600519.SH" in s for s in compiled_stmts)
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_tasks_with_date_filters(self) -> None:
        """Test 6: list_tasks filters by created_after and created_before."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        call_count = 0
        compiled_stmts = []

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            compiled_stmts.append(compiled)
            if call_count == 1:
                return count_result
            return data_result

        mock_session.execute = _mock_execute

        repo = PipelineTaskRepository(mock_session)
        after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        before = datetime(2024, 12, 31, tzinfo=timezone.utc)
        tasks, total = await repo.list_tasks(created_after=after, created_before=before)

        # Both date filters should appear
        assert any("2024-01-01" in s for s in compiled_stmts)
        assert any("2024-12-31" in s for s in compiled_stmts)

    @pytest.mark.asyncio
    async def test_list_tasks_ordering(self) -> None:
        """Test 7: list_tasks orders by created_at desc."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        mock_session = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        call_count = 0
        compiled_stmts = []

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            compiled_stmts.append(compiled)
            if call_count == 1:
                return count_result
            return data_result

        mock_session.execute = _mock_execute

        repo = PipelineTaskRepository(mock_session)
        tasks, total = await repo.list_tasks()

        # Second statement (data query) should have DESC ordering
        data_query = compiled_stmts[1] if len(compiled_stmts) > 1 else ""
        assert "DESC" in data_query.upper()


class TestPipelineConfigSandbox:
    """Tests for PipelineConfig sandbox fields."""

    def test_pipeline_config_sandbox_defaults(self) -> None:
        """Test 8: PipelineConfig has sandbox_enabled=False and sandbox_timeout=30 by default."""
        from stockvaluefinder.pipeline.config import PipelineConfig

        config = PipelineConfig()
        assert config.sandbox_enabled is False
        assert config.sandbox_timeout == 30

    def test_pipeline_config_sandbox_timeout_validation(self) -> None:
        """Test 9: PipelineConfig rejects sandbox_timeout less than 1."""
        from stockvaluefinder.pipeline.config import PipelineConfig

        with pytest.raises(ValueError, match="sandbox_timeout"):
            PipelineConfig(sandbox_timeout=0)


class TestPydanticModels:
    """Tests for new Pydantic models."""

    def test_trigger_request_valid(self) -> None:
        """Test: TriggerRequest accepts valid input."""
        from stockvaluefinder.pipeline.models import TriggerRequest

        req = TriggerRequest(ticker="600519.SH")
        assert req.ticker == "600519.SH"
        assert req.fiscal_year is None
        assert req.report_type is None

    def test_trigger_request_with_all_fields(self) -> None:
        """Test: TriggerRequest accepts all fields."""
        from stockvaluefinder.pipeline.models import TriggerRequest

        req = TriggerRequest(ticker="600519.SH", fiscal_year=2023, report_type="annual")
        assert req.fiscal_year == 2023
        assert req.report_type == "annual"

    def test_trigger_request_invalid_ticker(self) -> None:
        """Test: TriggerRequest rejects invalid ticker."""
        from pydantic import ValidationError

        from stockvaluefinder.pipeline.models import TriggerRequest

        with pytest.raises(ValidationError):
            TriggerRequest(ticker="INVALID")

    def test_task_list_item_response(self) -> None:
        """Test: TaskListItemResponse model works."""
        from stockvaluefinder.pipeline.models import TaskListItemResponse

        now = datetime.now(timezone.utc)
        item = TaskListItemResponse(
            task_id="abc-123",
            ticker="600519.SH",
            business_key="600519.SH:2023:annual",
            state="pending",
            current_stage=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        assert item.task_id == "abc-123"
        assert item.state == "pending"

    def test_pipeline_status_response(self) -> None:
        """Test: PipelineStatusResponse model works."""
        from stockvaluefinder.pipeline.models import PipelineStatusResponse

        resp = PipelineStatusResponse(
            counts={
                "pending": 1,
                "downloading": 0,
                "parsing": 0,
                "analyzing": 0,
                "done": 5,
                "failed": 0,
            },
            last_poll_time="2024-01-01T00:00:00Z",
            next_poll_time="2024-01-01T09:00:00Z",
            total_tasks=6,
        )
        assert resp.total_tasks == 6
        assert resp.counts["pending"] == 1


# ===================================================================
# Task 2: API Endpoint Tests
# ===================================================================


class TestStatusEndpoint:
    """Tests for GET /api/v1/pipeline/status endpoint."""

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_counts(self) -> None:
        """Test 1: GET /status returns 200 with counts dict containing all 6 states."""
        mock_session = _mock_db_session()
        mock_counts = {
            "pending": 1,
            "downloading": 0,
            "parsing": 2,
            "analyzing": 0,
            "done": 5,
            "failed": 1,
        }
        mock_watcher_state = MagicMock()
        mock_watcher_state.last_poll_time = datetime(
            2024, 5, 1, 9, 0, 0, tzinfo=timezone.utc
        )

        with (
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.count_by_state",
                new_callable=AsyncMock,
                return_value=mock_counts,
            ),
            patch(
                "stockvaluefinder.pipeline.watcher_repo.WatcherStateRepository.get_state",
                new_callable=AsyncMock,
                return_value=mock_watcher_state,
            ),
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "counts" in data["data"]
            assert set(data["data"]["counts"].keys()) == {
                "pending",
                "downloading",
                "parsing",
                "analyzing",
                "done",
                "failed",
            }
            assert "total_tasks" in data["data"]
            assert data["data"]["total_tasks"] == 9

    @pytest.mark.asyncio
    async def test_status_endpoint_computes_next_poll_time(self) -> None:
        """Test 9: GET /status computes next_poll_time from PipelineConfig cron schedules."""
        mock_session = _mock_db_session()
        mock_counts = {
            "pending": 0,
            "downloading": 0,
            "parsing": 0,
            "analyzing": 0,
            "done": 0,
            "failed": 0,
        }
        mock_watcher_state = MagicMock()
        # Use a known last_poll_time
        mock_watcher_state.last_poll_time = datetime(
            2024, 5, 1, 9, 0, 0, tzinfo=timezone.utc
        )

        with (
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.count_by_state",
                new_callable=AsyncMock,
                return_value=mock_counts,
            ),
            patch(
                "stockvaluefinder.pipeline.watcher_repo.WatcherStateRepository.get_state",
                new_callable=AsyncMock,
                return_value=mock_watcher_state,
            ),
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/status")

            data = response.json()
            assert data["data"]["next_poll_time"] is not None
            # next_poll_time should be an ISO string after last_poll_time
            assert data["data"]["last_poll_time"] == "2024-05-01T09:00:00+00:00"


class TestTasksEndpoint:
    """Tests for GET /api/v1/pipeline/tasks endpoint."""

    @pytest.mark.asyncio
    async def test_tasks_endpoint_default_pagination(self) -> None:
        """Test 2: GET /tasks returns 200 with tasks list and pagination meta."""
        mock_session = _mock_db_session()
        task1 = _make_pipeline_task_db(
            ticker="600519.SH", business_key="600519.SH:2023:annual", state="done"
        )
        task2 = _make_pipeline_task_db(
            ticker="000001.SZ", business_key="000001.SZ:2023:annual", state="pending"
        )

        with patch(
            "stockvaluefinder.pipeline.repo.PipelineTaskRepository.list_tasks",
            new_callable=AsyncMock,
            return_value=([task1, task2], 2),
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/pipeline/tasks")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]) == 2
            assert data["meta"]["total"] == 2
            assert data["meta"]["page"] == 1
            assert data["meta"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_tasks_endpoint_with_filters(self) -> None:
        """Test 3: GET /tasks accepts state, ticker, page, limit query params."""
        mock_session = _mock_db_session()

        with patch(
            "stockvaluefinder.pipeline.repo.PipelineTaskRepository.list_tasks",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as mock_list:
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/v1/pipeline/tasks",
                    params={
                        "state": "done",
                        "ticker": "600519.SH",
                        "page": 2,
                        "limit": 10,
                    },
                )

            assert response.status_code == 200
            mock_list.assert_awaited_once()
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["state"] == "done"
            assert call_kwargs["ticker"] == "600519.SH"
            assert call_kwargs["offset"] == 10
            assert call_kwargs["limit"] == 10


class TestTriggerEndpoint:
    """Tests for POST /api/v1/pipeline/trigger endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_creates_task_and_enqueues(self) -> None:
        """Test 4: POST /trigger creates task, auto-adds to watchlist, enqueues download_report."""
        mock_session = _mock_db_session()
        new_task = _make_pipeline_task_db()

        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock()

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.add",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.get_by_business_key",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.create_task",
                new_callable=AsyncMock,
                return_value=new_task,
            ),
        ):
            app = _create_app()
            app.state.arq_pool = mock_arq_pool
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/trigger",
                    json={"ticker": "600519.SH"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "task_id" in data["data"]
            # Verify enqueue_job was called with download_report
            mock_arq_pool.enqueue_job.assert_awaited_once()
            call_args = mock_arq_pool.enqueue_job.call_args
            assert call_args[0][0] == "download_report"

    @pytest.mark.asyncio
    async def test_trigger_dedup_done_task(self) -> None:
        """Test 5: POST /trigger returns error when DONE task already exists and force=false."""
        mock_session = _mock_db_session()
        existing_task = _make_pipeline_task_db(state="done")

        with patch(
            "stockvaluefinder.pipeline.repo.PipelineTaskRepository.get_by_business_key",
            new_callable=AsyncMock,
            return_value=existing_task,
        ):
            app = _create_app()
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/trigger",
                    json={"ticker": "600519.SH"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "already completed" in data["error"]

    @pytest.mark.asyncio
    async def test_trigger_force_bypass_dedup(self) -> None:
        """Test 6: POST /trigger with force=true reprocesses even if DONE task exists."""
        mock_session = _mock_db_session()
        existing_task = _make_pipeline_task_db(state="done")
        new_task = _make_pipeline_task_db()

        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock()

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.get_by_business_key",
                new_callable=AsyncMock,
                return_value=existing_task,
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.create_task",
                new_callable=AsyncMock,
                return_value=new_task,
            ) as mock_create,
        ):
            app = _create_app()
            app.state.arq_pool = mock_arq_pool
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/trigger?force=true",
                    json={"ticker": "600519.SH"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # create_task should have been called (new task created)
            mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trigger_with_fiscal_year(self) -> None:
        """Test 7: POST /trigger with fiscal_year and report_type uses those values."""
        mock_session = _mock_db_session()
        new_task = _make_pipeline_task_db(
            business_key="600519.SH:2023:annual",
        )

        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock()

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.get_by_business_key",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.create_task",
                new_callable=AsyncMock,
                return_value=new_task,
            ) as mock_create,
        ):
            app = _create_app()
            app.state.arq_pool = mock_arq_pool
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/trigger",
                    json={
                        "ticker": "600519.SH",
                        "fiscal_year": 2023,
                        "report_type": "annual",
                    },
                )

            assert response.status_code == 200
            # business_key should be "600519.SH:2023:annual"
            call_args = mock_create.call_args
            assert call_args[0][0] == "600519.SH"
            assert call_args[0][1] == "600519.SH:2023:annual"

    @pytest.mark.asyncio
    async def test_trigger_without_fiscal_year_defaults(self) -> None:
        """Test 8: POST /trigger omits fiscal_year defaults to current year and report_type to annual."""
        mock_session = _mock_db_session()
        new_task = _make_pipeline_task_db()

        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock()

        current_year = datetime.now().year
        expected_key = f"600519.SH:{current_year}:annual"

        with (
            patch(
                "stockvaluefinder.pipeline.watchlist_repo.WatchlistRepository.get_by_ticker",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.get_by_business_key",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "stockvaluefinder.pipeline.repo.PipelineTaskRepository.create_task",
                new_callable=AsyncMock,
                return_value=new_task,
            ) as mock_create,
        ):
            app = _create_app()
            app.state.arq_pool = mock_arq_pool
            app.dependency_overrides[GET_DB_DEPENDENCY] = _override_get_db(mock_session)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/pipeline/trigger",
                    json={"ticker": "600519.SH"},
                )

            assert response.status_code == 200
            call_args = mock_create.call_args
            assert call_args[0][1] == expected_key
