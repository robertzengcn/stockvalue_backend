"""Unit tests for WatcherService, helpers, and AKShare disclosure methods."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestGetCurrentReportPeriods:
    """Tests for get_current_report_periods helper."""

    def test_january_returns_annual_and_q1(self) -> None:
        """January returns previous year annual and current year Q1."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 1, 15, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 2
        assert ("2024\u5e74\u62a5", "annual", 2024) in periods
        assert ("2025\u4e00\u5b63", "q1", 2025) in periods

    def test_april_returns_annual_and_q1(self) -> None:
        """April (last high season month) returns annual and Q1."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 4, 30, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 2
        assert ("2024\u5e74\u62a5", "annual", 2024) in periods
        assert ("2025\u4e00\u5b63", "q1", 2025) in periods

    def test_july_returns_semi_annual(self) -> None:
        """July returns current year semi-annual."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 7, 15, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 1
        assert ("2025\u534a\u5e74\u62a5", "semi_annual", 2025) in periods

    def test_august_returns_semi_annual(self) -> None:
        """August returns current year semi-annual."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 8, 31, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 1
        assert ("2025\u534a\u5e74\u62a5", "semi_annual", 2025) in periods

    def test_october_returns_q3(self) -> None:
        """October returns current year Q3."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 10, 15, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 1
        assert ("2025\u4e09\u5b63", "q3", 2025) in periods

    def test_november_returns_q3(self) -> None:
        """November returns current year Q3."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 11, 30, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 1
        assert ("2025\u4e09\u5b63", "q3", 2025) in periods

    def test_december_returns_annual(self) -> None:
        """December returns previous year annual (early filers)."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 12, 1, tzinfo=timezone.utc)
        periods = get_current_report_periods(now)

        assert len(periods) == 1
        assert ("2024\u5e74\u62a5", "annual", 2024) in periods

    def test_may_june_return_empty(self) -> None:
        """May and June have no active reporting periods."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        may = datetime(2025, 5, 15, tzinfo=timezone.utc)
        june = datetime(2025, 6, 15, tzinfo=timezone.utc)

        assert get_current_report_periods(may) == []
        assert get_current_report_periods(june) == []

    def test_september_returns_empty(self) -> None:
        """September has no active reporting periods."""
        from stockvaluefinder.pipeline.watcher import get_current_report_periods

        now = datetime(2025, 9, 15, tzinfo=timezone.utc)
        assert get_current_report_periods(now) == []


class TestNormalizeAkshareTicker:
    """Tests for normalize_akshare_ticker helper."""

    def test_shanghai_6xx(self) -> None:
        """6xx codes get .SH suffix."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("600519") == "600519.SH"

    def test_shenzhen_0xx(self) -> None:
        """0xx codes get .SZ suffix."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("000001") == "000001.SZ"

    def test_shenzhen_3xx(self) -> None:
        """3xx codes get .SZ suffix."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("300001") == "300001.SZ"

    def test_with_exchange_shanghai(self) -> None:
        """Uses exchange hint for Shanghai."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("600519", "\u4e0a\u6d77") == "600519.SH"

    def test_with_exchange_shenzhen(self) -> None:
        """Uses exchange hint for Shenzhen."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("000001", "\u6df1\u5733") == "000001.SZ"

    def test_strips_whitespace(self) -> None:
        """Strips whitespace from code."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker(" 600519 ") == "600519.SH"

    def test_zero_pads_short_codes(self) -> None:
        """Zero-pads codes shorter than 6 digits."""
        from stockvaluefinder.pipeline.watcher import normalize_akshare_ticker

        assert normalize_akshare_ticker("1") == "000001.SZ"


class TestBuildBusinessKey:
    """Tests for build_business_key helper."""

    def test_standard_format(self) -> None:
        """build_business_key produces ticker:fiscal_year:report_type."""
        from stockvaluefinder.pipeline.watcher import build_business_key

        key = build_business_key("600519.SH", 2023, "annual")
        assert key == "600519.SH:2023:annual"

    def test_different_report_types(self) -> None:
        """build_business_key works for all report types."""
        from stockvaluefinder.pipeline.watcher import build_business_key

        assert build_business_key("000001.SZ", 2024, "q1") == "000001.SZ:2024:q1"
        assert (
            build_business_key("600519.SH", 2024, "semi_annual")
            == "600519.SH:2024:semi_annual"
        )
        assert build_business_key("600519.SH", 2024, "q3") == "600519.SH:2024:q3"


# ---------------------------------------------------------------------------
# AKShareClient disclosure method tests
# ---------------------------------------------------------------------------


class TestGetReportDisclosures:
    """Tests for AKShareClient.get_report_disclosures."""

    @pytest.mark.asyncio
    async def test_calls_stock_report_disclosure(self) -> None:
        """get_report_disclosures calls ak.stock_report_disclosure with correct params."""
        from stockvaluefinder.external.akshare_client import AKShareClient

        client = AKShareClient()
        client._available = True

        import pandas as pd  # type: ignore[import-untyped]

        mock_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519", "000001"],
                "\u80a1\u7968\u540d\u79f0": ["Kweichow Moutai", "Ping An Bank"],
                "\u9996\u6b21\u9884\u7ea6": [date(2024, 3, 15), date(2024, 3, 10)],
                "\u5b9e\u9645\u62ab\u9732": [date(2024, 4, 30), date(2024, 4, 20)],
            }
        )

        with patch("akshare.stock_report_disclosure", return_value=mock_df):
            result = await client.get_report_disclosures("2024\u5e74\u62a5")

        assert len(result) == 2
        assert result[0]["\u80a1\u7968\u4ee3\u7801"] == "600519"

    @pytest.mark.asyncio
    async def test_filters_nat_disclosure_dates(self) -> None:
        """get_report_disclosures filters out rows where actual_disclosure is NaT."""
        from stockvaluefinder.external.akshare_client import AKShareClient

        client = AKShareClient()
        client._available = True

        import pandas as pd  # type: ignore[import-untyped]

        mock_df = pd.DataFrame(
            {
                "\u80a1\u7968\u4ee3\u7801": ["600519", "000002"],
                "\u80a1\u7968\u540d\u79f0": ["Moutai", "NotYet"],
                "\u9996\u6b21\u9884\u7ea6": [date(2024, 3, 15), date(2024, 3, 10)],
                "\u5b9e\u9645\u62ab\u9732": [date(2024, 4, 30), pd.NaT],
            }
        )

        with patch("akshare.stock_report_disclosure", return_value=mock_df):
            result = await client.get_report_disclosures("2024\u5e74\u62a5")

        assert len(result) == 1
        assert result[0]["\u80a1\u7968\u4ee3\u7801"] == "600519"

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_df(self) -> None:
        """get_report_disclosures returns empty list for empty DataFrame."""
        from stockvaluefinder.external.akshare_client import AKShareClient

        client = AKShareClient()
        client._available = True

        import pandas as pd  # type: ignore[import-untyped]

        with patch("akshare.stock_report_disclosure", return_value=pd.DataFrame()):
            result = await client.get_report_disclosures("2024\u5e74\u62a5")

        assert result == []


class TestGetCninfoAnnouncements:
    """Tests for AKShareClient.get_cninfo_announcements."""

    @pytest.mark.asyncio
    async def test_calls_cninfo_function(self) -> None:
        """get_cninfo_announcements calls the correct AKShare function."""
        from stockvaluefinder.external.akshare_client import AKShareClient

        client = AKShareClient()
        client._available = True

        import pandas as pd  # type: ignore[import-untyped]

        mock_df = pd.DataFrame(
            {
                "\u4ee3\u7801": ["000001"],
                "\u7b80\u79f0": ["Ping An Bank"],
                "\u516c\u544a\u6807\u9898": ["2023 Annual Report"],
                "\u516c\u544a\u65f6\u95f4": [datetime(2024, 4, 20)],
            }
        )

        with patch("akshare.stock_zh_a_disclosure_report_cninfo", return_value=mock_df):
            result = await client.get_cninfo_announcements(
                symbol="000001",
                category="\u5e74\u62a5",
            )

        assert len(result) == 1


class TestGetIndexConstituents:
    """Tests for AKShareClient.get_index_constituents."""

    @pytest.mark.asyncio
    async def test_calls_index_stock_cons_csindex(self) -> None:
        """get_index_constituents calls ak.index_stock_cons_csindex."""
        from stockvaluefinder.external.akshare_client import AKShareClient

        client = AKShareClient()
        client._available = True

        import pandas as pd  # type: ignore[import-untyped]

        mock_df = pd.DataFrame(
            {
                "\u6210\u5206\u5238\u4ee3\u7801": ["600519", "000001"],
                "\u6210\u5206\u5238\u540d\u79f0": ["Kweichow Moutai", "Ping An Bank"],
            }
        )

        with patch("akshare.index_stock_cons_csindex", return_value=mock_df):
            result = await client.get_index_constituents(symbol="000300")

        assert len(result) == 2


# ---------------------------------------------------------------------------
# WatcherService.poll_disclosures tests
# ---------------------------------------------------------------------------


class TestPollDisclosures:
    """Tests for WatcherService.poll_disclosures."""

    @pytest.mark.asyncio
    async def test_polls_akshare_and_stages_disclosures(self) -> None:
        """poll_disclosures reads watchlist, polls AKShare, stages results."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_akshare.get_report_disclosures = AsyncMock(
            return_value=[
                {
                    "\u80a1\u7968\u4ee3\u7801": "600519",
                    "\u80a1\u7968\u540d\u79f0": "Moutai",
                    "\u9996\u6b21\u9884\u7ea6": date(2024, 3, 15),
                    "\u5b9e\u9645\u62ab\u9732": date(2024, 4, 30),
                }
            ]
        )

        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        mock_periods = [("2024\u5e74\u62a5", "annual", 2024)]

        with (
            patch.object(service, "_get_active_tickers", return_value=["600519.SH"]),
            patch(
                "stockvaluefinder.pipeline.watcher.get_current_report_periods",
                return_value=mock_periods,
            ),
            patch.object(service, "_stage_disclosures", return_value=1),
            patch.object(service, "_update_watcher_state", return_value=MagicMock()),
            patch.object(service, "_enqueue_process_disclosures", return_value=True),
        ):
            result = await service.poll_disclosures()

        assert result.staged_count == 1

    @pytest.mark.asyncio
    async def test_skips_poll_when_watchlist_empty(self) -> None:
        """poll_disclosures skips poll and logs warning when watchlist is empty (D-14)."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        with (
            patch.object(service, "_get_active_tickers", return_value=[]),
            patch.object(service, "_update_watcher_state", return_value=MagicMock()),
        ):
            result = await service.poll_disclosures()

        assert result.staged_count == 0
        mock_akshare.get_report_disclosures.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_cninfo_on_akshare_failure(self) -> None:
        """poll_disclosures falls back to CNInfo when AKShare fails (D-02)."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_akshare.get_report_disclosures = AsyncMock(
            side_effect=Exception("AKShare failed")
        )
        mock_akshare.get_cninfo_announcements = AsyncMock(
            return_value=[
                {
                    "\u4ee3\u7801": "600519",
                    "\u7b80\u79f0": "Moutai",
                    "\u516c\u544a\u6807\u9898": "2023 Annual Report",
                    "\u516c\u544a\u65f6\u95f4": datetime(2024, 4, 30),
                }
            ]
        )

        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        mock_periods = [("2024\u5e74\u62a5", "annual", 2024)]

        with (
            patch.object(service, "_get_active_tickers", return_value=["600519.SH"]),
            patch(
                "stockvaluefinder.pipeline.watcher.get_current_report_periods",
                return_value=mock_periods,
            ),
            patch.object(service, "_stage_disclosures", return_value=1),
            patch.object(service, "_update_watcher_state", return_value=MagicMock()),
            patch.object(service, "_enqueue_process_disclosures", return_value=True),
        ):
            result = await service.poll_disclosures()

        assert result.cninfo_fallback is True

    @pytest.mark.asyncio
    async def test_never_raises_on_error(self) -> None:
        """poll_disclosures never raises -- catches and logs errors."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        with (
            patch.object(
                service, "_get_active_tickers", side_effect=RuntimeError("DB error")
            ),
            patch.object(service, "_update_watcher_state", return_value=MagicMock()),
        ):
            # Should NOT raise
            result = await service.poll_disclosures()

        assert result.staged_count == 0


# ---------------------------------------------------------------------------
# WatcherService.process_disclosures tests
# ---------------------------------------------------------------------------


class TestProcessDisclosures:
    """Tests for WatcherService.process_disclosures."""

    @pytest.mark.asyncio
    async def test_creates_task_for_new_report(self) -> None:
        """process_disclosures creates a task for a new disclosure (D-10)."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        # Mock unprocessed disclosure
        disclosure = MagicMock()
        disclosure.disclosure_id = str(uuid4())
        disclosure.ticker = "600519.SH"
        disclosure.report_type = "annual"
        disclosure.fiscal_year = 2023
        disclosure.disclosure_date = date(2024, 4, 30)
        disclosure.stock_name = "Moutai"
        disclosure.source = "akshare"
        disclosure.source_raw = None

        with (
            patch.object(service, "_get_unprocessed", return_value=[disclosure]),
            patch.object(service, "_check_existing_task", return_value=None),
            patch.object(
                service,
                "_create_task",
                return_value=MagicMock(task_id=str(uuid4())),
            ),
            patch.object(service, "_mark_processed", return_value=1),
            patch.object(service, "_enqueue_download_job", return_value=True),
        ):
            result = await service.process_disclosures(str(uuid4()))

        assert result.new_count == 1
        assert result.amendment_count == 0
        assert result.skip_count == 0

    @pytest.mark.asyncio
    async def test_detects_amendment_via_later_disclosure_date(self) -> None:
        """process_disclosures detects amendment via disclosure_date (D-06)."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        # Existing task with earlier disclosure date
        existing_task = MagicMock()
        existing_task.disclosure_date = date(2024, 4, 15)

        # New disclosure with LATER disclosure date = amendment
        disclosure = MagicMock()
        disclosure.disclosure_id = str(uuid4())
        disclosure.ticker = "600519.SH"
        disclosure.report_type = "annual"
        disclosure.fiscal_year = 2023
        disclosure.disclosure_date = date(2024, 4, 30)
        disclosure.stock_name = "Moutai"
        disclosure.source = "akshare"
        disclosure.source_raw = None

        with (
            patch.object(service, "_get_unprocessed", return_value=[disclosure]),
            patch.object(service, "_check_existing_task", return_value=existing_task),
            patch.object(
                service,
                "_create_task",
                return_value=MagicMock(task_id=str(uuid4())),
            ),
            patch.object(service, "_mark_processed", return_value=1),
            patch.object(service, "_enqueue_download_job", return_value=True),
        ):
            result = await service.process_disclosures(str(uuid4()))

        assert result.amendment_count == 1
        assert result.new_count == 0

    @pytest.mark.asyncio
    async def test_skips_when_same_or_earlier_date(self) -> None:
        """process_disclosures skips when disclosure_date is same or earlier."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        # Existing task with same disclosure date
        existing_task = MagicMock()
        existing_task.disclosure_date = date(2024, 4, 30)

        disclosure = MagicMock()
        disclosure.disclosure_id = str(uuid4())
        disclosure.ticker = "600519.SH"
        disclosure.report_type = "annual"
        disclosure.fiscal_year = 2023
        disclosure.disclosure_date = date(2024, 4, 30)
        disclosure.stock_name = "Moutai"
        disclosure.source = "akshare"
        disclosure.source_raw = None

        with (
            patch.object(service, "_get_unprocessed", return_value=[disclosure]),
            patch.object(service, "_check_existing_task", return_value=existing_task),
            patch.object(service, "_mark_processed", return_value=1),
        ):
            result = await service.process_disclosures(str(uuid4()))

        assert result.skip_count == 1
        assert result.new_count == 0
        assert result.amendment_count == 0

    @pytest.mark.asyncio
    async def test_enqueues_one_arq_job_per_new_disclosure(self) -> None:
        """process_disclosures enqueues one arq job per new disclosure (D-12)."""
        from stockvaluefinder.external.akshare_client import AKShareClient
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.watcher import WatcherService

        config = PipelineConfig()
        mock_akshare = MagicMock(spec=AKShareClient)
        mock_session = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        service = WatcherService(
            akshare_client=mock_akshare,
            session_factory=mock_session_factory,
            config=config,
        )

        # Two new disclosures
        d1 = MagicMock()
        d1.disclosure_id = str(uuid4())
        d1.ticker = "600519.SH"
        d1.report_type = "annual"
        d1.fiscal_year = 2023
        d1.disclosure_date = date(2024, 4, 30)
        d1.stock_name = "Moutai"
        d1.source = "akshare"
        d1.source_raw = None

        d2 = MagicMock()
        d2.disclosure_id = str(uuid4())
        d2.ticker = "000001.SZ"
        d2.report_type = "annual"
        d2.fiscal_year = 2023
        d2.disclosure_date = date(2024, 4, 20)
        d2.stock_name = "Ping An"
        d2.source = "akshare"
        d2.source_raw = None

        enqueue_mock = AsyncMock(return_value=True)

        with (
            patch.object(service, "_get_unprocessed", return_value=[d1, d2]),
            patch.object(service, "_check_existing_task", return_value=None),
            patch.object(
                service,
                "_create_task",
                return_value=MagicMock(task_id=str(uuid4())),
            ),
            patch.object(service, "_mark_processed", return_value=2),
            patch.object(service, "_enqueue_download_job", enqueue_mock),
        ):
            result = await service.process_disclosures(str(uuid4()))

        assert result.new_count == 2
        assert enqueue_mock.call_count == 2
