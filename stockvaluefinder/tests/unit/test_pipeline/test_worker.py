"""Unit tests for arq worker skeleton (WorkerSettings, stub jobs, reaper cron)."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# WorkerSettings structure tests
# ---------------------------------------------------------------------------


class TestWorkerSettingsStructure:
    """Tests for WorkerSettings class attributes and configuration."""

    def test_functions_has_three_entries(self) -> None:
        """WorkerSettings.functions has 3 job functions."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "functions")
        assert len(WorkerSettings.functions) == 3

    def test_cron_jobs_has_one_entry(self) -> None:
        """WorkerSettings.cron_jobs has 1 cron job."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "cron_jobs")
        assert len(WorkerSettings.cron_jobs) == 1

    def test_has_on_startup(self) -> None:
        """WorkerSettings has on_startup function."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "on_startup")
        assert callable(WorkerSettings.on_startup)

    def test_has_on_shutdown(self) -> None:
        """WorkerSettings has on_shutdown function."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "on_shutdown")
        assert callable(WorkerSettings.on_shutdown)

    def test_has_redis_settings(self) -> None:
        """WorkerSettings has redis_settings attribute."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "redis_settings")


# ---------------------------------------------------------------------------
# on_startup / on_shutdown tests
# ---------------------------------------------------------------------------


class TestWorkerLifecycle:
    """Tests for worker startup and shutdown hooks."""

    @pytest.mark.asyncio
    async def test_on_startup_sets_http_client(self) -> None:
        """on_startup sets ctx['http_client'] to an httpx.AsyncClient."""
        from stockvaluefinder.pipeline.worker import on_startup

        ctx: dict = {}
        await on_startup(ctx)

        assert "http_client" in ctx
        # Verify it has async methods (httpx.AsyncClient)
        assert hasattr(ctx["http_client"], "aclose")

    @pytest.mark.asyncio
    async def test_on_startup_sets_session_factory(self) -> None:
        """on_startup sets ctx['session_factory'] to async_session_maker."""
        from stockvaluefinder.pipeline.worker import on_startup

        ctx: dict = {}
        await on_startup(ctx)

        assert "session_factory" in ctx
        assert callable(ctx["session_factory"])

    @pytest.mark.asyncio
    async def test_on_shutdown_closes_http_client(self) -> None:
        """on_shutdown closes ctx['http_client'] via await aclose()."""
        from stockvaluefinder.pipeline.worker import on_shutdown

        mock_client = AsyncMock()
        ctx = {"http_client": mock_client}
        await on_shutdown(ctx)

        mock_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Stub job function tests
# ---------------------------------------------------------------------------


class TestStubJobFunctions:
    """Tests for stub job functions (download_report, parse_report, analyze_report)."""

    @pytest.mark.asyncio
    async def test_download_report_runs_without_error(self) -> None:
        """download_report stub runs without raising errors."""
        from stockvaluefinder.pipeline.worker import download_report

        ctx: dict = {}
        # Should not raise
        await download_report(ctx, "test-task-id")

    @pytest.mark.asyncio
    async def test_parse_report_runs_without_error(self) -> None:
        """parse_report stub runs without raising errors."""
        from stockvaluefinder.pipeline.worker import parse_report

        ctx: dict = {}
        await parse_report(ctx, "test-task-id")

    @pytest.mark.asyncio
    async def test_analyze_report_runs_without_error(self) -> None:
        """analyze_report stub runs without raising errors."""
        from stockvaluefinder.pipeline.worker import analyze_report

        ctx: dict = {}
        await analyze_report(ctx, "test-task-id")


# ---------------------------------------------------------------------------
# reap_stuck_tasks tests
# ---------------------------------------------------------------------------


class TestReapStuckTasks:
    """Tests for reap_stuck_tasks cron function."""

    @pytest.mark.asyncio
    async def test_reap_resets_stuck_tasks(self) -> None:
        """reap_stuck_tasks queries stuck tasks and resets them."""
        from stockvaluefinder.pipeline.worker import reap_stuck_tasks

        # Create mock tasks
        stuck_task = MagicMock()
        stuck_task.task_id = "test-id"
        stuck_task.retry_count = 1
        stuck_task.max_retries = 3

        # Create mock repo
        mock_repo = MagicMock()
        mock_repo.get_stuck_tasks = AsyncMock(return_value=[stuck_task])
        mock_repo.reset_task = AsyncMock(return_value=stuck_task)

        # Create mock session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        # Create mock session factory
        mock_session_factory = MagicMock(return_value=mock_session)
        # Make it an async context manager
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"session_factory": mock_session_factory}

        with patch(
            "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
            return_value=mock_repo,
        ):
            await reap_stuck_tasks(ctx)

        mock_repo.get_stuck_tasks.assert_called_once()
        mock_repo.reset_task.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    async def test_reap_handles_errors_gracefully(self) -> None:
        """reap_stuck_tasks logs errors without crashing."""
        from stockvaluefinder.pipeline.worker import reap_stuck_tasks

        # Create mock session factory that raises
        mock_session_factory = MagicMock()

        async def raise_error():
            raise RuntimeError("DB connection failed")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=RuntimeError("DB connection failed")
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        ctx = {"session_factory": mock_session_factory}

        # Should NOT raise -- errors are caught and logged
        await reap_stuck_tasks(ctx)

    @pytest.mark.asyncio
    async def test_reap_logs_count_of_reaped_tasks(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """reap_stuck_tasks logs the number of reaped tasks."""
        from stockvaluefinder.pipeline.worker import reap_stuck_tasks

        stuck_task = MagicMock()
        stuck_task.task_id = "test-id"

        mock_repo = MagicMock()
        mock_repo.get_stuck_tasks = AsyncMock(return_value=[stuck_task])
        mock_repo.reset_task = AsyncMock(return_value=stuck_task)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"session_factory": mock_session_factory}

        with (
            caplog.at_level(logging.INFO),
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
        ):
            await reap_stuck_tasks(ctx)

        # Verify something was logged about reaping
        log_messages = [r.message for r in caplog.records]
        assert any(
            "reap" in msg.lower() or "stuck" in msg.lower() for msg in log_messages
        )
