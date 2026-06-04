"""Scan orchestrator for the Market Index Value Scanner.

This module provides the ScanOrchestrator async service class that wires
together all Phase 25-27 components into a complete scan pipeline:

    1. Create scan run -> fetch constituents -> batch market data
    2. Coarse screen -> rank -> top N selection
    3. Deep analysis per stock (DCF, risk, quality review)
    4. Composite scoring -> reason generation -> candidate persistence

Design principles:
    - DCF valuation runs only on top-N stocks from coarse screen
    - Per-stock failure isolation (one failure does not abort the scan)
    - asyncio.Semaphore for concurrency control on deep analysis
    - Scan run transitions: pending -> running -> completed | partial_failed
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from stockvaluefinder.market_scanner.batch_data_fetcher import BatchDataFetcher
from stockvaluefinder.market_scanner.composite_scorer import calculate_composite_score
from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import (
    CandidateReasons,
    CompositeScore,
    ScreeningSnapshot,
)
from stockvaluefinder.market_scanner.quality_review import review_stock_quality
from stockvaluefinder.market_scanner.reason_generator import generate_reasons
from stockvaluefinder.market_scanner.coarse_screener import (
    rank_screened_stocks,
    screen_stocks,
)
from stockvaluefinder.models.enums import ScanType
from stockvaluefinder.models.market_scanner import (
    MarketScanCandidateCreate,
    MarketScanRunCreate,
)
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.models.valuation import DCFParams, ValuationResult
from stockvaluefinder.repositories.index_constituent_repo import (
    IndexConstituentRepository,
)
from stockvaluefinder.repositories.market_scan_repo import (
    MarketScanCandidateRepository,
    MarketScanRunRepository,
)
from stockvaluefinder.services.risk_service import analyze_financial_risk
from stockvaluefinder.services.valuation_service import analyze_dcf_valuation

logger = logging.getLogger(__name__)


@dataclass
class StockAnalysisResult:
    """Internal accumulator for a single stock's deep analysis outcome.

    Mutable by design -- used as an accumulator within the orchestrator.
    Not frozen because it is built incrementally during analysis.

    Attributes:
        ticker: Stock code.
        passed: Whether the stock passed all quality gates.
        composite_score: Composite scoring result (None if failed).
        reasons: Structured selection reasons and risk flags.
        valuation_result: DCF valuation result.
        risk_score: Risk analysis result.
        snapshot: Original market data snapshot.
    """

    ticker: str
    passed: bool
    composite_score: CompositeScore | None = None
    reasons: CandidateReasons | None = None
    valuation_result: ValuationResult | None = None
    risk_score: RiskScore | None = None
    snapshot: ScreeningSnapshot | None = None


class ScanOrchestrator:
    """Async service that orchestrates the full scan pipeline.

    Wires together constituent lookup, batch data fetch, coarse screen,
    deep analysis (DCF, risk, quality review), composite scoring, reason
    generation, and candidate persistence.

    Usage::

        orchestrator = ScanOrchestrator(
            config=config,
            data_service=data_service,
            run_repo=run_repo,
            candidate_repo=candidate_repo,
            constituent_repo=constituent_repo,
            batch_fetcher=batch_fetcher,
        )
        run_id = await orchestrator.run_scan("CSI300", ScanType.DAILY)
    """

    def __init__(
        self,
        config: MarketScannerConfig,
        data_service: Any,
        run_repo: MarketScanRunRepository,
        candidate_repo: MarketScanCandidateRepository,
        constituent_repo: IndexConstituentRepository,
        batch_fetcher: BatchDataFetcher,
    ) -> None:
        """Initialize the scan orchestrator.

        Args:
            config: Scanner configuration with thresholds and weights.
            data_service: ExternalDataService for financial data fetching.
            run_repo: Repository for scan run lifecycle management.
            candidate_repo: Repository for candidate persistence.
            constituent_repo: Repository for index constituent lookup.
            batch_fetcher: BatchDataFetcher for bulk market data.
        """
        self.config = config
        self.data_service = data_service
        self.run_repo = run_repo
        self.candidate_repo = candidate_repo
        self.constituent_repo = constituent_repo
        self.batch_fetcher = batch_fetcher
        self._logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )
        self._stock_errors: dict[str, str] = {}

    async def run_scan(
        self,
        index_code: str,
        scan_type: ScanType = ScanType.DAILY,
    ) -> UUID:
        """Execute the full scan pipeline for a given index.

        Pipeline steps:
            1. Create scan run (pending) and transition to running
            2. Get active constituents for index_code
            3. Fetch market snapshots via batch API
            4. Run coarse screen on all snapshots
            5. Rank and select top-N stocks
            6. Deep analysis on each top-N stock with failure isolation
            7. Persist passing candidates
            8. Mark run completed or partial_failed

        Args:
            index_code: Index pool identifier (e.g., CSI300, CSI500).
            scan_type: Scan frequency type (daily or weekly).

        Returns:
            UUID of the created scan run.
        """
        self._stock_errors = {}
        run_id = uuid4()

        # Step 1: Create scan run and transition to running
        create_data = MarketScanRunCreate(
            run_id=run_id,
            index_codes=(index_code,),
            scan_type=scan_type,
            rules_version=self.config.rules_version,
            total_count=0,
        )
        await self.run_repo.create_run(create_data)
        await self.run_repo.mark_running(run_id)

        # Step 2: Get active constituents
        constituents = await self.constituent_repo.get_active_by_index(index_code)
        tickers = {c.ticker for c in constituents}

        # Step 3: Fetch market snapshots
        snapshots_dict = await self.batch_fetcher.fetch_market_snapshots(
            tickers, self.config,
        )

        # Step 4: Coarse screen
        snapshots = list(snapshots_dict.values())
        results = screen_stocks(snapshots, self.config)

        # Step 5: Rank and select top-N
        top_n = (
            self.config.daily_top_n
            if scan_type == ScanType.DAILY
            else self.config.weekly_top_n
        )
        top_results = rank_screened_stocks(results, top_n)

        # Step 6: Deep analysis with failure isolation
        analysis_results: list[StockAnalysisResult] = []
        for top_result in top_results:
            snapshot = snapshots_dict.get(top_result.ticker)
            if snapshot is None:
                self._stock_errors[top_result.ticker] = "Snapshot not found"
                continue
            result = await self._analyze_single_stock(top_result.ticker, snapshot)
            if result is not None:
                analysis_results.append(result)

        # Step 7: Collect passed candidates and persist
        passed_results = [
            r for r in analysis_results
            if r.passed
            and r.composite_score is not None
            and r.composite_score.passed_threshold
        ]

        for passed_result in passed_results:
            # Type narrowing: passed_results filter ensures composite_score is not None
            assert passed_result.composite_score is not None  # noqa: S101
            candidate_data = MarketScanCandidateCreate(
                candidate_id=uuid4(),
                run_id=run_id,
                ticker=passed_result.ticker,
                index_code=index_code,
                passed=True,
                composite_score=passed_result.composite_score.composite,
                screening_snapshot=_build_screening_snapshot(passed_result),
            )
            await self.candidate_repo.create(candidate_data)

        # Step 8: Mark run completed or partial_failed
        error_summary: dict[str, Any] = {}
        if self._stock_errors:
            error_summary["stock_errors"] = dict(self._stock_errors)
        if self.batch_fetcher.errors:
            error_summary["fetch_errors"] = dict(self.batch_fetcher.errors)

        if error_summary:
            await self.run_repo.mark_partial_failed(
                run_id,
                error_summary,
                total_count=len(tickers),
                screened_count=len(top_results),
                candidate_count=len(passed_results),
            )
        else:
            await self.run_repo.mark_completed(
                run_id,
                total_count=len(tickers),
                screened_count=len(top_results),
                candidate_count=len(passed_results),
            )

        return run_id

    async def _analyze_single_stock(
        self,
        ticker: str,
        snapshot: ScreeningSnapshot,
    ) -> StockAnalysisResult | None:
        """Run deep analysis for a single stock with failure isolation.

        Fetches financial data, runs DCF valuation, risk analysis, quality
        review, composite scoring, and reason generation. Any exception
        during analysis is caught and logged, and None is returned so the
        scan continues for other stocks.

        Args:
            ticker: Stock code.
            snapshot: Market data snapshot for this stock.

        Returns:
            StockAnalysisResult with all analysis data, or None if analysis
            failed (failure is isolated and logged).
        """
        try:
            # Fetch financial data (current and previous year)
            current_year = date.today().year - 1
            prev_year = current_year - 1

            financial = await self.data_service.get_financial_report(
                ticker, year=current_year,
            )
            prev_financial = await self.data_service.get_financial_report(
                ticker, year=prev_year,
            )

            # Fetch price, FCF, and shares
            price = await self.data_service.get_current_price(ticker)
            fcf = await self.data_service.get_free_cash_flow(ticker)
            shares = await self.data_service.get_shares_outstanding(ticker)

            # Build default DCF parameters
            dcf_params = DCFParams(
                risk_free_rate=0.028,
                beta=1.0,
                market_risk_premium=0.06,
                growth_rate_stage1=0.08,
                growth_rate_stage2=0.03,
                years_stage1=5,
                years_stage2=5,
                terminal_growth=0.025,
            )

            # Run DCF valuation
            valuation = analyze_dcf_valuation(
                ticker, price, fcf, shares, dcf_params, uuid4(),
            )

            # Check safety margin threshold
            if valuation.margin_of_safety < self.config.min_margin_of_safety:
                return StockAnalysisResult(
                    ticker=ticker,
                    passed=False,
                    snapshot=snapshot,
                )

            # Run risk analysis
            risk = analyze_financial_risk(financial, prev_financial)

            # Quality review gate
            quality = review_stock_quality(
                valuation_result=valuation,
                risk_score=risk,
            )
            if not quality.passed:
                return StockAnalysisResult(
                    ticker=ticker,
                    passed=False,
                    snapshot=snapshot,
                )

            # Composite scoring
            composite = calculate_composite_score(
                margin_of_safety=valuation.margin_of_safety,
                alpha_score=None,
                risk_level=risk.risk_level,
                yield_gap_value=None,
                valuation_percentile=None,
                config=self.config,
            )

            # Generate reasons
            reasons = generate_reasons(
                composite_score=composite,
                valuation_result=valuation,
                risk_score=risk,
            )

            return StockAnalysisResult(
                ticker=ticker,
                passed=True,
                composite_score=composite,
                reasons=reasons,
                valuation_result=valuation,
                risk_score=risk,
                snapshot=snapshot,
            )

        except Exception as e:
            self._logger.warning(f"Analysis failed for {ticker}: {e}")
            self._stock_errors[ticker] = str(e)
            return None


def _build_screening_snapshot(result: StockAnalysisResult) -> dict[str, Any]:
    """Build a JSONB-serializable snapshot from analysis results.

    Args:
        result: Analysis result for a passing candidate.

    Returns:
        Dictionary suitable for screening_snapshot JSONB column.
    """
    snapshot: dict[str, Any] = {
        "ticker": result.ticker,
        "passed": result.passed,
    }
    if result.composite_score is not None:
        snapshot["composite_score"] = result.composite_score.composite
        snapshot["passed_threshold"] = result.composite_score.passed_threshold
        snapshot["components"] = result.composite_score.components.model_dump()
    if result.valuation_result is not None:
        snapshot["margin_of_safety"] = result.valuation_result.margin_of_safety
        snapshot["intrinsic_value"] = float(result.valuation_result.intrinsic_value)
        snapshot["wacc"] = result.valuation_result.wacc
    if result.risk_score is not None:
        snapshot["risk_level"] = result.risk_score.risk_level.value
        snapshot["m_score"] = result.risk_score.m_score
        snapshot["f_score"] = result.risk_score.f_score
    if result.reasons is not None:
        snapshot["reasons"] = result.reasons.reasons
        snapshot["risk_flags"] = result.reasons.risk_flags
    if result.snapshot is not None:
        snapshot["market_data"] = result.snapshot.model_dump()
    return snapshot


__all__ = ["ScanOrchestrator", "StockAnalysisResult"]
