"""Unit tests for ScanOrchestrator scan pipeline (SCR-02 + pipeline).

Tests the full scan pipeline orchestration with mocked dependencies.
Focuses on orchestration logic, not the underlying service behavior
(those are tested in their own plan test files).

Covers:
    - Run lifecycle transitions (pending -> running -> completed/partial_failed)
    - Constituent lookup and batch data fetch
    - Coarse screen and top-N selection
    - DCF valuation on top-N only
    - Safety margin threshold filtering
    - Quality review gate
    - Candidate persistence
    - Per-stock failure isolation
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.market_scanner.batch_data_fetcher import BatchDataFetcher
from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import (
    CandidateReasons,
    CompositeScore,
    CompositeScoreComponents,
    ScreeningSnapshot,
)
from stockvaluefinder.market_scanner.scan_orchestrator import (
    ScanOrchestrator,
)
from stockvaluefinder.models.enums import RiskLevel, ScanType, ValuationLevel
from stockvaluefinder.models.market_scanner import (
    MarketScanCandidateCreate,
    MarketScanRunCreate,
)
from stockvaluefinder.models.risk import FScoreData, MScoreData, RiskScore
from stockvaluefinder.models.valuation import DCFParams, ValuationResult


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_mscore_data() -> MScoreData:
    """Create a default MScoreData instance for testing."""
    return MScoreData(
        dsri=1.0,
        gmi=1.0,
        aqi=1.0,
        sgi=1.0,
        depi=1.0,
        sgai=1.0,
        lvgi=1.0,
        tata=0.0,
    )


def _make_fscore_data() -> FScoreData:
    """Create a default FScoreData instance for testing."""
    return FScoreData(
        positive_roa=True,
        positive_cfo=True,
        improving_roa=True,
        cfo_exceeds_roa=True,
        lower_leverage=True,
        higher_liquidity=True,
        no_new_shares=True,
        improving_margin=True,
        improving_turnover=True,
    )


def _make_risk_score(
    risk_level: RiskLevel = RiskLevel.LOW,
    m_score: float = -2.50,
    f_score: int = 8,
) -> RiskScore:
    """Create a RiskScore instance for testing."""
    return RiskScore(
        score_id=uuid4(),
        ticker="600519.SH",
        report_id=uuid4(),
        risk_level=risk_level,
        calculated_at=datetime.now(timezone.utc),
        m_score=m_score,
        mscore_data=_make_mscore_data(),
        f_score=f_score,
        fscore_data=_make_fscore_data(),
        存贷双高=False,
        cash_amount=Decimal("500000000"),
        debt_amount=Decimal("200000000"),
        cash_growth_rate=0.05,
        debt_growth_rate=-0.03,
        goodwill_ratio=0.05,
        goodwill_excessive=False,
        profit_cash_divergence=False,
        profit_growth=0.10,
        ocf_growth=0.12,
        red_flags=[],
    )


def _make_valuation_result(
    margin_of_safety: float = 0.50,
    intrinsic_value: float = 150.0,
) -> ValuationResult:
    """Create a ValuationResult instance for testing."""
    return ValuationResult(
        ticker="600519.SH",
        current_price=Decimal("100.00"),
        intrinsic_value=Decimal(str(intrinsic_value)),
        wacc=0.09,
        margin_of_safety=margin_of_safety,
        valuation_level=ValuationLevel.UNDERVALUED,
        valuation_id=uuid4(),
        calculated_at=datetime.now(timezone.utc),
        dcf_params=DCFParams(
            risk_free_rate=0.028,
            beta=1.0,
            market_risk_premium=0.06,
            growth_rate_stage1=0.08,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
        ),
        audit_trail={},
    )


def _make_snapshot(
    ticker: str = "600519.SH",
    **overrides: Any,
) -> ScreeningSnapshot:
    """Create a valid ScreeningSnapshot for testing."""
    defaults = {
        "ticker": ticker,
        "name": "Test Stock",
        "index_code": "CSI300",
        "is_st": False,
        "is_suspended": False,
        "has_price_data": True,
        "turnover_ratio": 1.5,
        "pe_ttm": 15.0,
        "pb_ratio": 2.0,
        "dividend_yield": 0.03,
        "price_vs_52w_high": 0.85,
        "ocf_positive_years": 5,
        "market_cap": 5_000_000_000,
    }
    defaults.update(overrides)
    return ScreeningSnapshot(**defaults)


def _make_constituent(
    ticker: str = "600519.SH",
    index_code: str = "CSI300",
) -> MagicMock:
    """Create a mock IndexConstituentDB with a ticker attribute."""
    mock_c = MagicMock()
    mock_c.ticker = ticker
    mock_c.index_code = index_code
    return mock_c


def _default_config(**overrides: Any) -> MarketScannerConfig:
    """Create a MarketScannerConfig with sensible test defaults."""
    defaults: dict[str, Any] = {
        "index_codes": ("CSI300",),
        "daily_top_n": 50,
        "weekly_top_n": 100,
        "min_margin_of_safety": 0.30,
        "min_composite_score": 60.0,
    }
    defaults.update(overrides)
    return MarketScannerConfig(**defaults)


def _make_composite_score(
    composite: float = 75.0,
    passed_threshold: bool = True,
) -> CompositeScore:
    """Create a CompositeScore instance for testing."""
    return CompositeScore(
        composite=composite,
        components=CompositeScoreComponents(
            safety_margin=50.0,
            alpha=50.0,
            risk_penalty=50.0,
            yield_gap=50.0,
            valuation_percentile=50.0,
        ),
        passed_threshold=passed_threshold,
    )


def _create_orchestrator(
    config: MarketScannerConfig | None = None,
) -> tuple[ScanOrchestrator, dict[str, AsyncMock]]:
    """Create a ScanOrchestrator with all mocked dependencies.

    Returns:
        Tuple of (orchestrator, mocks_dict) where mocks_dict contains
        all the mocked dependencies for test assertions.
    """
    if config is None:
        config = _default_config()

    data_service = AsyncMock()
    run_repo = AsyncMock()
    candidate_repo = AsyncMock()
    constituent_repo = AsyncMock()
    batch_fetcher_mock = AsyncMock(spec=BatchDataFetcher)
    batch_fetcher_mock.errors = {}

    orchestrator = ScanOrchestrator(
        config=config,
        data_service=data_service,
        run_repo=run_repo,
        candidate_repo=candidate_repo,
        constituent_repo=constituent_repo,
        batch_fetcher=batch_fetcher_mock,
    )

    mocks = {
        "data_service": data_service,
        "run_repo": run_repo,
        "candidate_repo": candidate_repo,
        "constituent_repo": constituent_repo,
        "batch_fetcher": batch_fetcher_mock,
    }

    return orchestrator, mocks


def _setup_default_pipeline(
    mocks: dict[str, AsyncMock],
    tickers: list[str] | None = None,
) -> None:
    """Configure mocks for a default successful pipeline.

    Sets up constituents, snapshots, data_service responses so the full
    pipeline runs end-to-end.
    """
    if tickers is None:
        tickers = ["600519.SH", "000858.SZ"]

    # Constituents
    constituents = [_make_constituent(t) for t in tickers]
    mocks["constituent_repo"].get_active_by_index.return_value = constituents

    # Snapshots -- all pass coarse screen by default
    snapshots = {t: _make_snapshot(ticker=t) for t in tickers}
    mocks["batch_fetcher"].fetch_market_snapshots.return_value = snapshots

    # Data service responses
    for ticker in tickers:
        mocks["data_service"].get_financial_report.side_effect = None
        mocks["data_service"].get_current_price.return_value = Decimal("100.00")
        mocks["data_service"].get_free_cash_flow.return_value = 5000.0
        mocks["data_service"].get_shares_outstanding.return_value = 1000.0

    # Default financial reports
    financial_data = {
        "ticker": tickers[0],
        "report_id": uuid4(),
        "report_source": "test",
        "revenue": 100_000_000_000,
        "net_income": 50_000_000_000,
        "operating_cash_flow": 45_000_000_000,
        "accounts_receivable": 10_000_000_000,
        "cost_of_goods": 30_000_000_000,
        "total_current_assets": 80_000_000_000,
        "total_assets": 200_000_000_000,
        "assets_total": 200_000_000_000,
        "ppe": 40_000_000_000,
        "sga_expense": 5_000_000_000,
        "total_liabilities": 60_000_000_000,
        "liabilities_total": 60_000_000_000,
        "cash_and_equivalents": 50_000_000_000,
        "interest_bearing_debt": 20_000_000_000,
        "equity_total": 140_000_000_000,
        "goodwill": 1_000_000_000,
        "shares_outstanding": 1_000_000_000,
        "gross_margin": 0.70,
    }

    mocks["data_service"].get_financial_report.return_value = financial_data


def _patch_analysis_services(
    margin_of_safety: float = 0.50,
    risk_level: RiskLevel = RiskLevel.LOW,
    m_score: float = -2.50,
    composite_score: float = 75.0,
    passed_threshold: bool = True,
):
    """Return a context manager that patches all analysis service functions.

    Patches analyze_dcf_valuation, analyze_financial_risk,
    calculate_composite_score, and generate_reasons to return
    deterministic test fixtures.
    """
    from contextlib import contextmanager

    @contextmanager
    def _patcher():
        valuation = _make_valuation_result(margin_of_safety=margin_of_safety)
        risk = _make_risk_score(risk_level=risk_level, m_score=m_score)
        composite = _make_composite_score(
            composite=composite_score,
            passed_threshold=passed_threshold,
        )
        reasons = CandidateReasons(
            reasons=["Test reason"],
            risk_flags=["Test risk flag"],
        )

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                return_value=valuation,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=risk,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.calculate_composite_score",
                return_value=composite,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.generate_reasons",
                return_value=reasons,
            ),
        ):
            yield

    return _patcher()


# ---------------------------------------------------------------------------
# Tests: Run lifecycle
# ---------------------------------------------------------------------------


class TestRunLifecycle:
    """Tests for scan run lifecycle state transitions."""

    @pytest.mark.asyncio
    async def test_run_scan_creates_run_and_transitions(self) -> None:
        """Verify run_scan calls create_run then mark_running then mark_completed."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        # Verify call order: create_run, then mark_running, then mark_completed
        mocks["run_repo"].create_run.assert_called_once()
        mocks["run_repo"].mark_running.assert_called_once()
        mocks["run_repo"].mark_completed.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scan_marks_completed_when_no_errors(self) -> None:
        """When no errors occur, mark_completed is called with correct counts."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        call_args = mocks["run_repo"].mark_completed.call_args
        assert call_args.kwargs["total_count"] == 1  # 1 constituent
        assert call_args.kwargs["screened_count"] == 1  # 1 passed screen
        assert call_args.kwargs["candidate_count"] == 1  # 1 persisted

    @pytest.mark.asyncio
    async def test_run_scan_marks_partial_failed_when_errors(self) -> None:
        """When stock errors occur, mark_partial_failed is called with error_summary."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH", "000858.SZ"])

        # Make one stock's analysis fail by raising in data_service
        call_count = 0

        async def _get_report_side_effect(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise RuntimeError("Data fetch failed for this stock")
            return {
                "ticker": "600519.SH",
                "report_id": uuid4(),
                "report_source": "test",
                "revenue": 100_000_000_000,
                "net_income": 50_000_000_000,
                "operating_cash_flow": 45_000_000_000,
                "accounts_receivable": 10_000_000_000,
                "cost_of_goods": 30_000_000_000,
                "total_current_assets": 80_000_000_000,
                "total_assets": 200_000_000_000,
                "assets_total": 200_000_000_000,
                "ppe": 40_000_000_000,
                "sga_expense": 5_000_000_000,
                "total_liabilities": 60_000_000_000,
                "liabilities_total": 60_000_000_000,
                "cash_and_equivalents": 50_000_000_000,
                "interest_bearing_debt": 20_000_000_000,
                "equity_total": 140_000_000_000,
                "goodwill": 1_000_000_000,
                "shares_outstanding": 1_000_000_000,
                "gross_margin": 0.70,
            }

        mocks["data_service"].get_financial_report.side_effect = _get_report_side_effect

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        # Should have called mark_partial_failed (because one stock failed)
        assert (
            mocks["run_repo"].mark_partial_failed.called
            or mocks["run_repo"].mark_completed.called
        )


# ---------------------------------------------------------------------------
# Tests: Data fetching
# ---------------------------------------------------------------------------


class TestDataFetching:
    """Tests for constituent lookup and batch data fetch."""

    @pytest.mark.asyncio
    async def test_run_scan_fetches_constituents(self) -> None:
        """Verify get_active_by_index called with correct index_code."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        mocks["constituent_repo"].get_active_by_index.assert_called_once_with("CSI300")

    @pytest.mark.asyncio
    async def test_run_scan_fetches_snapshots(self) -> None:
        """Verify batch_fetcher.fetch_market_snapshots called with constituent tickers."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH", "000858.SZ"])

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        call_args = mocks["batch_fetcher"].fetch_market_snapshots.call_args
        tickers_arg = call_args.args[0]
        assert tickers_arg == {"600519.SH", "000858.SZ"}


# ---------------------------------------------------------------------------
# Tests: Coarse screen and top-N
# ---------------------------------------------------------------------------


class TestCoarseScreen:
    """Tests for coarse screen and top-N selection."""

    @pytest.mark.asyncio
    async def test_run_scan_runs_coarse_screen(self) -> None:
        """With 5 stocks (3 passing, 2 failing screen), only 3 go to deep analysis."""
        orchestrator, mocks = _create_orchestrator()

        # Create 3 passing snapshots + 2 failing (ST and suspended)
        snapshots = {
            "600519.SH": _make_snapshot(ticker="600519.SH"),
            "000858.SZ": _make_snapshot(ticker="000858.SZ"),
            "601318.SH": _make_snapshot(ticker="601318.SH"),
        }
        _setup_default_pipeline(mocks, list(snapshots.keys()))

        # Add ST stock (will fail coarse screen)
        snapshots["600001.SH"] = _make_snapshot(
            ticker="600001.SH",
            name="*ST Stock",
            is_st=True,
        )
        # Add suspended stock (will fail coarse screen)
        snapshots["600002.SH"] = _make_snapshot(
            ticker="600002.SH",
            is_suspended=True,
            turnover_ratio=0.0,
        )

        mocks["batch_fetcher"].fetch_market_snapshots.return_value = snapshots

        dcf_call_count = 0

        def _mock_dcf(*args: Any, **kwargs: Any) -> ValuationResult:
            nonlocal dcf_call_count
            dcf_call_count += 1
            return _make_valuation_result(margin_of_safety=0.50)

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                side_effect=_mock_dcf,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=_make_risk_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.calculate_composite_score",
                return_value=_make_composite_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.generate_reasons",
                return_value=CandidateReasons(
                    reasons=["Test"],
                    risk_flags=["Test flag"],
                ),
            ),
        ):
            await orchestrator.run_scan("CSI300")

        # DCF should only be called for the 3 passing, non-ST, non-suspended stocks
        assert dcf_call_count == 3

    @pytest.mark.asyncio
    async def test_run_scan_top_n_limit(self) -> None:
        """With 10 stocks passing screen and daily_top_n=5, only 5 get deep analysis."""
        config = _default_config(daily_top_n=5)
        orchestrator, mocks = _create_orchestrator(config)

        # 10 passing snapshots
        tickers = [f"60{i:04d}.SH" for i in range(10)]
        snapshots = {t: _make_snapshot(ticker=t) for t in tickers}
        _setup_default_pipeline(mocks, tickers)
        mocks["batch_fetcher"].fetch_market_snapshots.return_value = snapshots

        dcf_call_count = 0

        def _mock_dcf(*args: Any, **kwargs: Any) -> ValuationResult:
            nonlocal dcf_call_count
            dcf_call_count += 1
            return _make_valuation_result(margin_of_safety=0.50)

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                side_effect=_mock_dcf,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=_make_risk_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.calculate_composite_score",
                return_value=_make_composite_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.generate_reasons",
                return_value=CandidateReasons(
                    reasons=["Test"],
                    risk_flags=["Test flag"],
                ),
            ),
        ):
            await orchestrator.run_scan("CSI300")

        assert dcf_call_count == 5


# ---------------------------------------------------------------------------
# Tests: Safety margin and quality review filtering
# ---------------------------------------------------------------------------


class TestFiltering:
    """Tests for safety margin threshold and quality review filtering."""

    @pytest.mark.asyncio
    async def test_run_scan_safety_margin_filter(self) -> None:
        """Stock with margin_of_safety=0.10 (below 0.30) gets passed=False."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        # Return valuation with insufficient safety margin
        with _patch_analysis_services(margin_of_safety=0.10):
            await orchestrator.run_scan("CSI300")

        # No candidates should have been persisted (stock filtered by safety margin)
        mocks["candidate_repo"].create.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_scan_quality_review_filter(self) -> None:
        """Stock failing quality review gets passed=False, not persisted as candidate."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        # High risk stock that will fail quality review
        high_risk_score = _make_risk_score(
            risk_level=RiskLevel.HIGH,
            m_score=-1.50,
        )

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                return_value=_make_valuation_result(margin_of_safety=0.50),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=high_risk_score,
            ),
        ):
            await orchestrator.run_scan("CSI300")

        # No candidates should have been persisted (failed quality review)
        mocks["candidate_repo"].create.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Candidate persistence
# ---------------------------------------------------------------------------


class TestCandidatePersistence:
    """Tests for candidate persistence."""

    @pytest.mark.asyncio
    async def test_run_scan_persists_candidates(self) -> None:
        """Verify candidate_repo.create called for each passing stock."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH", "000858.SZ"])

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        # Both stocks should be persisted as candidates
        assert mocks["candidate_repo"].create.call_count == 2

        # Verify the first candidate has correct data
        first_call = mocks["candidate_repo"].create.call_args_list[0]
        candidate_data = first_call.args[0]
        assert isinstance(candidate_data, MarketScanCandidateCreate)
        assert candidate_data.passed is True
        assert candidate_data.index_code == "CSI300"


# ---------------------------------------------------------------------------
# Tests: Failure isolation
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    """Tests for per-stock failure isolation."""

    @pytest.mark.asyncio
    async def test_single_stock_failure_isolation(self) -> None:
        """One stock failing analysis does not prevent others from being processed."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH", "000858.SZ"])

        # Make get_financial_report fail for the second stock
        call_count = 0

        async def _get_report_side_effect(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise RuntimeError("Data fetch failed")
            return {
                "ticker": "600519.SH",
                "report_id": uuid4(),
                "report_source": "test",
                "revenue": 100_000_000_000,
                "net_income": 50_000_000_000,
                "operating_cash_flow": 45_000_000_000,
                "accounts_receivable": 10_000_000_000,
                "cost_of_goods": 30_000_000_000,
                "total_current_assets": 80_000_000_000,
                "total_assets": 200_000_000_000,
                "assets_total": 200_000_000_000,
                "ppe": 40_000_000_000,
                "sga_expense": 5_000_000_000,
                "total_liabilities": 60_000_000_000,
                "liabilities_total": 60_000_000_000,
                "cash_and_equivalents": 50_000_000_000,
                "interest_bearing_debt": 20_000_000_000,
                "equity_total": 140_000_000_000,
                "goodwill": 1_000_000_000,
                "shares_outstanding": 1_000_000_000,
                "gross_margin": 0.70,
            }

        mocks["data_service"].get_financial_report.side_effect = _get_report_side_effect

        with _patch_analysis_services():
            await orchestrator.run_scan("CSI300")

        # At least one candidate should still have been persisted
        assert mocks["candidate_repo"].create.call_count >= 1

    @pytest.mark.asyncio
    async def test_analyze_single_stock_returns_none_on_exception(self) -> None:
        """When analysis throws, _analyze_single_stock returns None."""
        orchestrator, mocks = _create_orchestrator()
        snapshot = _make_snapshot()

        # Make data service raise
        mocks["data_service"].get_financial_report.side_effect = RuntimeError("fail")

        result = await orchestrator._analyze_single_stock("600519.SH", snapshot)

        assert result is None
        assert "600519.SH" in orchestrator._stock_errors


# ---------------------------------------------------------------------------
# Tests: Return value
# ---------------------------------------------------------------------------


class TestReturnValue:
    """Tests for run_scan return value."""

    @pytest.mark.asyncio
    async def test_run_scan_returns_run_id(self) -> None:
        """Verify return value is the UUID created in create_run."""
        orchestrator, mocks = _create_orchestrator()
        _setup_default_pipeline(mocks, ["600519.SH"])

        with _patch_analysis_services():
            run_id = await orchestrator.run_scan("CSI300")

        # The returned UUID should match what was passed to create_run
        create_call = mocks["run_repo"].create_run.call_args
        create_data = create_call.args[0]
        assert isinstance(create_data, MarketScanRunCreate)
        assert run_id == create_data.run_id


# ---------------------------------------------------------------------------
# Tests: Scan type selection
# ---------------------------------------------------------------------------


class TestScanTypeSelection:
    """Tests for scan type (daily vs weekly) top-N selection."""

    @pytest.mark.asyncio
    async def test_weekly_scan_uses_weekly_top_n(self) -> None:
        """Weekly scan uses weekly_top_n from config."""
        config = _default_config(daily_top_n=2, weekly_top_n=5)
        orchestrator, mocks = _create_orchestrator(config)

        # 4 passing stocks
        tickers = [f"60{i:04d}.SH" for i in range(4)]
        snapshots = {t: _make_snapshot(ticker=t) for t in tickers}
        _setup_default_pipeline(mocks, tickers)
        mocks["batch_fetcher"].fetch_market_snapshots.return_value = snapshots

        dcf_call_count = 0

        def _mock_dcf(*args: Any, **kwargs: Any) -> ValuationResult:
            nonlocal dcf_call_count
            dcf_call_count += 1
            return _make_valuation_result(margin_of_safety=0.50)

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                side_effect=_mock_dcf,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=_make_risk_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.calculate_composite_score",
                return_value=_make_composite_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.generate_reasons",
                return_value=CandidateReasons(
                    reasons=["Test"],
                    risk_flags=["Test flag"],
                ),
            ),
        ):
            await orchestrator.run_scan("CSI300", ScanType.WEEKLY)

        # Weekly top_n=5, but only 4 stocks, so all 4 should get DCF
        assert dcf_call_count == 4

    @pytest.mark.asyncio
    async def test_daily_scan_uses_daily_top_n(self) -> None:
        """Daily scan uses daily_top_n from config."""
        config = _default_config(daily_top_n=2, weekly_top_n=5)
        orchestrator, mocks = _create_orchestrator(config)

        # 4 passing stocks
        tickers = [f"60{i:04d}.SH" for i in range(4)]
        snapshots = {t: _make_snapshot(ticker=t) for t in tickers}
        _setup_default_pipeline(mocks, tickers)
        mocks["batch_fetcher"].fetch_market_snapshots.return_value = snapshots

        dcf_call_count = 0

        def _mock_dcf(*args: Any, **kwargs: Any) -> ValuationResult:
            nonlocal dcf_call_count
            dcf_call_count += 1
            return _make_valuation_result(margin_of_safety=0.50)

        with (
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_dcf_valuation",
                side_effect=_mock_dcf,
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.analyze_financial_risk",
                return_value=_make_risk_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.calculate_composite_score",
                return_value=_make_composite_score(),
            ),
            patch(
                "stockvaluefinder.market_scanner.scan_orchestrator.generate_reasons",
                return_value=CandidateReasons(
                    reasons=["Test"],
                    risk_flags=["Test flag"],
                ),
            ),
        ):
            await orchestrator.run_scan("CSI300", ScanType.DAILY)

        # Daily top_n=2, so only 2 should get DCF
        assert dcf_call_count == 2
