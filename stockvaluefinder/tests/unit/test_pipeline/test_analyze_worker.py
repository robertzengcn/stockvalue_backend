"""Unit tests for analyze_report worker function.

Tests cover:
- Successful analysis when all 3 analyzers pass
- Partial failure handling (one or more analyzers fail)
- Financial data fetching for 2 years (current + previous)
- AKShare column name mapping to analyzer input fields
- RAG fallback when AKShare data unavailable
- result_summary JSON structure per D-05
- Task state transitions (ANALYZING -> DONE or FAILED)
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.models.enums import (
    RiskLevel,
    ValuationLevel,
    YieldRecommendation,
)
from stockvaluefinder.models.valuation import DCFParams
from stockvaluefinder.pipeline.state import PipelineState


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_mock_risk_score():
    """Create a mock RiskScore result."""
    mock_score = MagicMock()
    mock_score.score_id = uuid4()
    mock_score.risk_level = RiskLevel.LOW
    mock_score.m_score = -2.5
    mock_score.f_score = 7
    mock_score.red_flags = []
    return mock_score


def _make_mock_valuation_result():
    """Create a mock ValuationResult."""
    mock_result = MagicMock()
    mock_result.valuation_id = uuid4()
    mock_result.intrinsic_value = Decimal("150.00")
    mock_result.wacc = 0.09
    mock_result.margin_of_safety = 0.5
    mock_result.valuation_level = ValuationLevel.UNDERVALUED
    return mock_result


def _make_mock_yield_gap():
    """Create a mock YieldGap result."""
    mock_gap = MagicMock()
    mock_gap.analysis_id = uuid4()
    mock_gap.yield_gap = 0.025
    mock_gap.recommendation = YieldRecommendation.ATTRACTIVE
    return mock_gap


def _make_akshare_income_data():
    """Sample AKShare income statement data (English columns)."""
    return {
        "TOTAL_OPERATE_INCOME": 1000000000,
        "NETPROFIT": 200000000,
        "OPERATE_COST": 600000000,
        "TOTAL_OPERATE_COST": 800000000,
    }


def _make_akshare_balance_data():
    """Sample AKShare balance sheet data (English columns)."""
    return {
        "TOTAL_ASSETS": 5000000000,
        "TOTAL_CURRENT_ASSETS": 2000000000,
        "ACCOUNTS_RECE": 300000000,
        "FIXED_ASSET": 1500000000,
        "TOTAL_LIABILITIES": 2000000000,
        "TOTAL_EQUITY": 3000000000,
        "MONETARYFUNDS": 500000000,
        "GOODWILL": 100000000,
        "INVENTORY": 200000000,
    }


def _make_akshare_cashflow_data():
    """Sample AKShare cash flow statement data (English columns)."""
    return {
        "NETCASH_OPERATE": 250000000,
    }


def _make_mock_task(business_key="600519.SH:2023:ANNUAL"):
    """Create a mock pipeline task."""
    task = MagicMock()
    task.task_id = uuid4()
    task.ticker = business_key.split(":")[0]
    task.business_key = business_key
    task.state = "analyzing"
    task.result_summary = None
    return task


def _make_mock_session_factory(mock_session):
    """Create a mock session factory that returns mock_session."""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _make_mock_session(mock_task=None):
    """Create a mock async session with commit and rollback."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _default_dcf_params():
    """Default DCF params for testing."""
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


# ---------------------------------------------------------------------------
# Test: successful_analysis_all_pass
# ---------------------------------------------------------------------------


class TestSuccessfulAnalysis:
    """Tests for analyze_report when all 3 analyzers succeed."""

    @pytest.mark.asyncio
    async def test_successful_analysis_all_pass(self) -> None:
        """All 3 analyzers succeed, task transitions ANALYZING->DONE."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        # Mock AKShare client to return valid data
        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        # Mock analyzers to return success
        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Verify task transitions to DONE
        done_calls = [
            call
            for call in mock_repo.transition_state.call_args_list
            if call[0][1] == PipelineState.DONE
        ]
        assert len(done_calls) == 1, "Task should transition to DONE"

    @pytest.mark.asyncio
    async def test_result_summary_has_three_success_entries(self) -> None:
        """result_summary contains 3 success entries when all pass."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        mock_risk_score = _make_mock_risk_score()
        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=mock_risk_score)

        mock_val_result = _make_mock_valuation_result()
        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=mock_val_result)

        mock_yield_gap = _make_mock_yield_gap()
        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=mock_yield_gap)

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Verify result_summary structure
        summary = mock_task.result_summary
        assert summary is not None, "result_summary should be set"
        assert "risk" in summary
        assert "valuation" in summary
        assert "yield" in summary
        assert summary["risk"]["status"] == "success"
        assert summary["valuation"]["status"] == "success"
        assert summary["yield"]["status"] == "success"
        assert "result_ref" in summary["risk"]
        assert "result_ref" in summary["valuation"]
        assert "result_ref" in summary["yield"]


# ---------------------------------------------------------------------------
# Test: partial_failure_risk_fails
# ---------------------------------------------------------------------------


class TestPartialFailure:
    """Tests for analyze_report partial failure handling."""

    @pytest.mark.asyncio
    async def test_partial_failure_risk_fails(self) -> None:
        """Risk analyzer raises, valuation and yield succeed, task goes FAILED."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(side_effect=ValueError("Risk analysis failed"))

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Task should transition to FAILED (any analyzer failed)
        failed_calls = [
            call
            for call in mock_repo.transition_state.call_args_list
            if call[0][1] == PipelineState.FAILED
        ]
        assert len(failed_calls) == 1, "Task should transition to FAILED"

        # result_summary should show risk=failed, valuation=success, yield=success
        summary = mock_task.result_summary
        assert summary["risk"]["status"] == "failed"
        assert "error" in summary["risk"]
        assert "Risk analysis failed" in summary["risk"]["error"]
        assert summary["valuation"]["status"] == "success"
        assert summary["yield"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_partial_failure_all_fail(self) -> None:
        """All 3 analyzers raise, task transitions to FAILED, 3 failed entries."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(side_effect=RuntimeError("Risk error"))

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(side_effect=RuntimeError("Valuation error"))

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(side_effect=RuntimeError("Yield error"))

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Task should transition to FAILED
        failed_calls = [
            call
            for call in mock_repo.transition_state.call_args_list
            if call[0][1] == PipelineState.FAILED
        ]
        assert len(failed_calls) == 1

        # All 3 should be failed
        summary = mock_task.result_summary
        assert summary["risk"]["status"] == "failed"
        assert summary["valuation"]["status"] == "failed"
        assert summary["yield"]["status"] == "failed"
        assert "Risk error" in summary["risk"]["error"]
        assert "Valuation error" in summary["valuation"]["error"]
        assert "Yield error" in summary["yield"]["error"]


# ---------------------------------------------------------------------------
# Test: financial_data_fetch_2_years
# ---------------------------------------------------------------------------


class TestFinancialDataFetch:
    """Tests for 2-year financial data fetching."""

    @pytest.mark.asyncio
    async def test_financial_data_fetch_2_years(self) -> None:
        """AKShare called with current and previous year periods."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task("600519.SH:2023:ANNUAL")
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Verify AKShare called with current year (20231231) and previous year (20221231)
        profit_calls = mock_akshare.get_profit_sheet.call_args_list
        assert len(profit_calls) == 2
        # First call = current year
        assert profit_calls[0][0][0] == "600519.SH"
        assert (
            profit_calls[0][1].get("period") == "20231231"
            or profit_calls[0][0][1] == "20231231"
        )
        # Second call = previous year
        assert profit_calls[1][0][0] == "600519.SH"
        assert (
            profit_calls[1][1].get("period") == "20221231"
            or profit_calls[1][0][1] == "20221231"
        )

    @pytest.mark.asyncio
    async def test_no_previous_year_data(self) -> None:
        """Previous year data returns empty, analysis still runs with None."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task("600519.SH:2023:ANNUAL")
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        # Current year returns data, previous year returns empty
        current_income = [_make_akshare_income_data()]
        current_balance = [_make_akshare_balance_data()]
        current_cashflow = [_make_akshare_cashflow_data()]

        call_count = [0]

        async def _profit_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                return []  # Previous year returns empty
            return current_income

        async def _balance_side_effect(*args, **kwargs):
            return (
                current_balance if mock_akshare.get_profit_sheet.call_count <= 1 else []
            )

        async def _cashflow_side_effect(*args, **kwargs):
            return (
                current_cashflow
                if mock_akshare.get_profit_sheet.call_count <= 1
                else []
            )

        mock_akshare.get_profit_sheet = AsyncMock(side_effect=_profit_side_effect)
        mock_akshare.get_balance_sheet = AsyncMock(side_effect=_balance_side_effect)
        mock_akshare.get_cash_flow_sheet = AsyncMock(side_effect=_cashflow_side_effect)

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Risk analyzer should be called with previous_report=None
        risk_call_args = mock_risk.analyze.call_args
        # Second positional arg is previous_report
        assert (
            risk_call_args[0][1] is None
            or risk_call_args[1].get("previous_report") is None
        )


# ---------------------------------------------------------------------------
# Test: akshare_data_mapping
# ---------------------------------------------------------------------------


class TestDataMapping:
    """Tests for AKShare column name mapping."""

    @pytest.mark.asyncio
    async def test_akshare_data_mapping(self) -> None:
        """AKShare column names correctly mapped to analyzer input fields."""
        from stockvaluefinder.pipeline.worker import _map_akshare_to_report

        income = _make_akshare_income_data()
        balance = _make_akshare_balance_data()
        cashflow = _make_akshare_cashflow_data()

        result = _map_akshare_to_report(income, balance, cashflow, "600519.SH", 2023)

        # Verify income mappings
        assert result["revenue"] == "1000000000"
        assert result["net_income"] == "200000000"
        assert result["cost_of_goods"] == "600000000"
        assert result["sga_expense"] == "800000000"

        # Verify balance sheet mappings
        assert result["assets_total"] == "5000000000"
        assert result["total_assets"] == "5000000000"
        assert result["total_current_assets"] == "2000000000"
        assert result["accounts_receivable"] == "300000000"
        assert result["ppe"] == "1500000000"
        assert result["total_liabilities"] == "2000000000"
        assert result["liabilities_total"] == "2000000000"
        assert result["equity_total"] == "3000000000"
        assert result["cash_and_equivalents"] == "500000000"
        assert result["goodwill"] == "100000000"

        # Verify cash flow mapping
        assert result["operating_cash_flow"] == "250000000"

        # Verify metadata
        assert result["ticker"] == "600519.SH"
        assert result["fiscal_year"] == 2023
        assert result["report_source"] == "AKShare"
        assert "report_id" in result


# ---------------------------------------------------------------------------
# Test: result_summary_json_structure
# ---------------------------------------------------------------------------


class TestResultSummaryStructure:
    """Tests for result_summary JSON structure per D-05."""

    @pytest.mark.asyncio
    async def test_result_summary_json_structure(self) -> None:
        """Summary matches D-05 format with per-analyzer status and result_ref."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        risk_id = uuid4()
        mock_risk_score = _make_mock_risk_score()
        mock_risk_score.score_id = risk_id
        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=mock_risk_score)

        val_id = uuid4()
        mock_val_result = _make_mock_valuation_result()
        mock_val_result.valuation_id = val_id
        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=mock_val_result)

        yield_id = uuid4()
        mock_yield_gap = _make_mock_yield_gap()
        mock_yield_gap.analysis_id = yield_id
        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=mock_yield_gap)

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        summary = mock_task.result_summary
        assert summary is not None

        # D-05 format: each entry has "status" and "result_ref" (on success)
        for analyzer_name in ["risk", "valuation", "yield"]:
            assert analyzer_name in summary
            entry = summary[analyzer_name]
            assert "status" in entry
            assert entry["status"] == "success"
            assert "result_ref" in entry
            # result_ref should be a string (UUID)
            assert isinstance(entry["result_ref"], str)


# ---------------------------------------------------------------------------
# Test: RAG fallback when AKShare fails
# ---------------------------------------------------------------------------


class TestRAGFallback:
    """Tests for RAG fallback when AKShare data unavailable."""

    @pytest.mark.asyncio
    async def test_rag_fallback_when_akshare_fails(self) -> None:
        """AKShare returns empty, RAG fallback provides data, analysis proceeds."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        # AKShare returns empty lists
        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(return_value=[])
        mock_akshare.get_balance_sheet = AsyncMock(return_value=[])
        mock_akshare.get_cash_flow_sheet = AsyncMock(return_value=[])

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        # RAG fallback returns valid data
        rag_report = {
            "ticker": "600519.SH",
            "fiscal_year": 2023,
            "revenue": "1000000000",
            "net_income": "200000000",
            "assets_total": "5000000000",
            "total_assets": "5000000000",
            "total_liabilities": "2000000000",
            "operating_cash_flow": "250000000",
            "report_source": "RAG",
        }

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._extract_from_rag",
                return_value=rag_report,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Task should transition to DONE (RAG fallback provided data)
        done_calls = [
            call
            for call in mock_repo.transition_state.call_args_list
            if call[0][1] == PipelineState.DONE
        ]
        assert len(done_calls) == 1

    @pytest.mark.asyncio
    async def test_rag_fallback_also_fails(self) -> None:
        """Both AKShare and RAG return None, task transitions to FAILED."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        # AKShare returns empty
        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(return_value=[])
        mock_akshare.get_balance_sheet = AsyncMock(return_value=[])
        mock_akshare.get_cash_flow_sheet = AsyncMock(return_value=[])

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker._extract_from_rag",
                return_value=None,
            ),
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # Task should transition to FAILED (no data available)
        failed_calls = [
            call
            for call in mock_repo.transition_state.call_args_list
            if call[0][1] == PipelineState.FAILED
        ]
        assert len(failed_calls) == 1
        # Check error message mentions data unavailability
        error_msg = failed_calls[0][1].get("error_message", "")
        assert error_msg is not None and (
            "financial data" in error_msg.lower()
            or "fetch" in error_msg.lower()
            or "current" in error_msg.lower()
        )


# ---------------------------------------------------------------------------
# Test: task not found
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases in analyze_report."""

    @pytest.mark.asyncio
    async def test_returns_early_when_task_not_found(self) -> None:
        """analyze_report returns early when task_id not found."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with patch(
            "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
            return_value=mock_repo,
        ):
            # Should not raise
            await analyze_report(ctx, "nonexistent-task-id")

        # No state transitions should happen
        mock_repo.transition_state.assert_not_called()


# ---------------------------------------------------------------------------
# Test: analyzers run via asyncio.to_thread
# ---------------------------------------------------------------------------


class TestAnalyzerExecution:
    """Tests that analyzers run in parallel via asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_sync_analyzers_wrapped_in_to_thread(self) -> None:
        """Sync analyzers are wrapped in asyncio.to_thread to prevent blocking."""
        from stockvaluefinder.pipeline.worker import analyze_report

        mock_task = _make_mock_task()
        mock_session = _make_mock_session()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_task)
        mock_repo.transition_state = AsyncMock()

        mock_akshare = AsyncMock()
        mock_akshare.get_profit_sheet = AsyncMock(
            return_value=[_make_akshare_income_data()]
        )
        mock_akshare.get_balance_sheet = AsyncMock(
            return_value=[_make_akshare_balance_data()]
        )
        mock_akshare.get_cash_flow_sheet = AsyncMock(
            return_value=[_make_akshare_cashflow_data()]
        )

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        ctx = {
            "session_factory": _make_mock_session_factory(mock_session),
        }

        with (
            patch(
                "stockvaluefinder.pipeline.worker.PipelineTaskRepository",
                return_value=mock_repo,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.AKShareClient",
                return_value=mock_akshare,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.asyncio.to_thread",
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
            ) as mock_to_thread,
        ):
            await analyze_report(ctx, str(mock_task.task_id))

        # asyncio.to_thread should be called 3 times (once per analyzer)
        assert mock_to_thread.call_count == 3
