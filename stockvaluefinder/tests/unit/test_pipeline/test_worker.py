"""Unit tests for arq worker (WorkerSettings, stub jobs, reaper cron, watcher cron)."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# WorkerSettings structure tests
# ---------------------------------------------------------------------------


class TestWorkerSettingsStructure:
    """Tests for WorkerSettings class attributes and configuration."""

    def test_functions_includes_process_disclosures(self) -> None:
        """WorkerSettings.functions includes process_disclosures alongside stubs."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        function_names = [f.__name__ for f in WorkerSettings.functions]
        assert "process_disclosures" in function_names

    def test_functions_has_four_entries(self) -> None:
        """WorkerSettings.functions has 4 job functions (3 stubs + process_disclosures)."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "functions")
        assert len(WorkerSettings.functions) == 4

    def test_cron_jobs_has_two_entries(self) -> None:
        """WorkerSettings.cron_jobs has 2 cron jobs (reaper + watch_disclosures)."""
        from stockvaluefinder.pipeline.worker import WorkerSettings

        assert hasattr(WorkerSettings, "cron_jobs")
        assert len(WorkerSettings.cron_jobs) == 2

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
    async def test_on_startup_creates_watcher_instance(self) -> None:
        """on_startup creates WatcherService and stores in ctx dict."""
        from stockvaluefinder.pipeline.worker import on_startup

        ctx: dict = {}
        await on_startup(ctx)

        assert "watcher" in ctx

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
    """Tests for stub job functions (parse_report, analyze_report) and download_report."""

    @pytest.mark.asyncio
    async def test_download_report_returns_when_task_not_found(self) -> None:
        """download_report returns early without error when task not found."""
        from stockvaluefinder.pipeline.worker import download_report

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=None)

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"session_factory": mock_session_factory}

        with patch(
            "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
            return_value=mock_task_repo,
        ):
            # Should not raise -- returns early when task not found
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


# ---------------------------------------------------------------------------
# watch_disclosures cron tests
# ---------------------------------------------------------------------------


class TestWatchDisclosures:
    """Tests for watch_disclosures cron function."""

    @pytest.mark.asyncio
    async def test_skips_off_season_non_monday(self) -> None:
        """watch_disclosures skips when off-season and not Monday (D-07, D-08)."""
        from stockvaluefinder.pipeline.worker import watch_disclosures

        mock_watcher = MagicMock()
        mock_watcher.poll_disclosures = AsyncMock(
            return_value=MagicMock(staged_count=0)
        )

        ctx = {"watcher": mock_watcher}

        # Patch datetime to be June (off-season) and a Wednesday (weekday=2)
        june_wed = datetime(2025, 6, 11, 9, 0, tzinfo=timezone.utc)
        with patch("stockvaluefinder.pipeline.worker.datetime") as mock_dt:
            mock_dt.now.return_value = june_wed
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await watch_disclosures(ctx)

        mock_watcher.poll_disclosures.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_poll_in_high_season(self) -> None:
        """watch_disclosures calls poll_disclosures during high season (D-07)."""
        from stockvaluefinder.pipeline.worker import watch_disclosures

        mock_watcher = MagicMock()
        mock_watcher.poll_disclosures = AsyncMock(
            return_value=MagicMock(staged_count=5)
        )

        ctx = {"watcher": mock_watcher}

        # March is in high_season_months {1,2,3,4}
        march_tue = datetime(2025, 3, 11, 9, 0, tzinfo=timezone.utc)
        with patch("stockvaluefinder.pipeline.worker.datetime") as mock_dt:
            mock_dt.now.return_value = march_tue
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await watch_disclosures(ctx)

        mock_watcher.poll_disclosures.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_poll_on_monday_off_season(self) -> None:
        """watch_disclosures calls poll on Monday during off-season (D-08)."""
        from stockvaluefinder.pipeline.worker import watch_disclosures

        mock_watcher = MagicMock()
        mock_watcher.poll_disclosures = AsyncMock(
            return_value=MagicMock(staged_count=0)
        )

        ctx = {"watcher": mock_watcher}

        # June is off-season, Monday is weekday=0
        june_mon = datetime(2025, 6, 9, 9, 0, tzinfo=timezone.utc)
        with patch("stockvaluefinder.pipeline.worker.datetime") as mock_dt:
            mock_dt.now.return_value = june_mon
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await watch_disclosures(ctx)

        mock_watcher.poll_disclosures.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_watcher_in_context(self) -> None:
        """watch_disclosures handles missing watcher gracefully."""
        from stockvaluefinder.pipeline.worker import watch_disclosures

        ctx: dict = {}

        # Should not raise
        march = datetime(2025, 3, 11, 9, 0, tzinfo=timezone.utc)
        with patch("stockvaluefinder.pipeline.worker.datetime") as mock_dt:
            mock_dt.now.return_value = march
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await watch_disclosures(ctx)

    @pytest.mark.asyncio
    async def test_never_raises_on_error(self) -> None:
        """watch_disclosures catches errors and never raises."""
        from stockvaluefinder.pipeline.worker import watch_disclosures

        mock_watcher = MagicMock()
        mock_watcher.poll_disclosures = AsyncMock(
            side_effect=RuntimeError("Poll failed")
        )

        ctx = {"watcher": mock_watcher}

        # Should NOT raise
        march = datetime(2025, 3, 11, 9, 0, tzinfo=timezone.utc)
        with patch("stockvaluefinder.pipeline.worker.datetime") as mock_dt:
            mock_dt.now.return_value = march
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await watch_disclosures(ctx)


# ---------------------------------------------------------------------------
# process_disclosures function tests
# ---------------------------------------------------------------------------


class TestProcessDisclosures:
    """Tests for process_disclosures job function."""

    @pytest.mark.asyncio
    async def test_calls_watcher_process_disclosures(self) -> None:
        """process_disclosures reads poll_id from args, calls WatcherService."""
        from stockvaluefinder.pipeline.worker import process_disclosures

        mock_watcher = MagicMock()
        mock_watcher.process_disclosures = AsyncMock(
            return_value=MagicMock(new_count=2, amendment_count=0, skip_count=1)
        )

        poll_id = "test-poll-id-123"
        ctx = {"watcher": mock_watcher}

        await process_disclosures(ctx, poll_id)

        mock_watcher.process_disclosures.assert_awaited_once_with(poll_id)

    @pytest.mark.asyncio
    async def test_catches_and_logs_exceptions(self) -> None:
        """process_disclosures catches exceptions and does not re-raise."""
        from stockvaluefinder.pipeline.worker import process_disclosures

        mock_watcher = MagicMock()
        mock_watcher.process_disclosures = AsyncMock(
            side_effect=RuntimeError("Processing failed")
        )

        ctx = {"watcher": mock_watcher}

        # Should NOT raise
        await process_disclosures(ctx, "test-poll-id")

    @pytest.mark.asyncio
    async def test_handles_missing_watcher_gracefully(self) -> None:
        """process_disclosures handles missing watcher in context."""
        from stockvaluefinder.pipeline.worker import process_disclosures

        ctx: dict = {}

        # Should NOT raise
        await process_disclosures(ctx, "test-poll-id")
