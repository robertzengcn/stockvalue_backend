"""Unit tests for coarse_screener module.

Tests cover all hard-exclusion rules, soft prioritization signals,
batch screening, and ranking functionality.
"""

from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.coarse_screener import (
    _compute_rank_score,
    rank_screened_stocks,
    screen_stock,
    screen_stocks,
)
from stockvaluefinder.market_scanner.models import ScreeningResult, ScreeningSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides: object) -> ScreeningSnapshot:
    """Create a ScreeningSnapshot with sensible defaults.

    Any field can be overridden via kwargs.
    """
    defaults = {
        "ticker": "600519.SH",
        "name": "Test Stock",
        "index_code": "CSI300",
        "is_st": False,
        "is_suspended": False,
        "has_price_data": True,
        "turnover_ratio": 0.05,
        "pe_ttm": 15.0,
        "pb_ratio": 2.0,
        "dividend_yield": 0.03,
        "price_vs_52w_high": 0.8,
        "ocf_positive_years": 5,
        "market_cap": 5_000_000_000,
    }
    defaults.update(overrides)
    return ScreeningSnapshot(**defaults)  # type: ignore[arg-type]


def _default_config() -> MarketScannerConfig:
    """Return a default MarketScannerConfig."""
    return MarketScannerConfig()


# ---------------------------------------------------------------------------
# Test 1: ST stock is excluded
# ---------------------------------------------------------------------------


class TestSTStockExclusion:
    """ST stocks must always be excluded regardless of other metrics."""

    def test_excludes_st_stock(self) -> None:
        snapshot = _make_snapshot(is_st=True)
        result = screen_stock(snapshot, _default_config())
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "ST stock" in result.excluded_reason


# ---------------------------------------------------------------------------
# Test 2: Suspended stock is excluded
# ---------------------------------------------------------------------------


class TestSuspendedStockExclusion:
    """Suspended stocks must be excluded."""

    def test_excludes_suspended_stock(self) -> None:
        snapshot = _make_snapshot(is_suspended=True)
        result = screen_stock(snapshot, _default_config())
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "Suspended" in result.excluded_reason


# ---------------------------------------------------------------------------
# Test 3: Missing price data is excluded
# ---------------------------------------------------------------------------


class TestMissingPriceDataExclusion:
    """Stocks without price data must be excluded."""

    def test_excludes_missing_price_data(self) -> None:
        snapshot = _make_snapshot(has_price_data=False)
        result = screen_stock(snapshot, _default_config())
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "Missing price data" in result.excluded_reason


# ---------------------------------------------------------------------------
# Test 4: Below min turnover ratio is excluded (liquidity)
# ---------------------------------------------------------------------------


class TestLowLiquidityExclusion:
    """Stocks below min_turnover_ratio are excluded for low liquidity."""

    def test_excludes_below_min_turnover_ratio(self) -> None:
        snapshot = _make_snapshot(turnover_ratio=0.001)
        config = MarketScannerConfig(min_turnover_ratio=0.01)
        result = screen_stock(snapshot, config)
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "liquidity" in result.excluded_reason.lower()


# ---------------------------------------------------------------------------
# Test 5: Insufficient positive OCF years is excluded (cash flow)
# ---------------------------------------------------------------------------


class TestNegativeCashFlowExclusion:
    """Stocks with insufficient positive OCF years are excluded."""

    def test_excludes_insufficient_ocf_years(self) -> None:
        snapshot = _make_snapshot(ocf_positive_years=1)
        config = MarketScannerConfig(min_ocf_positive_years=2)
        result = screen_stock(snapshot, config)
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "cash flow" in result.excluded_reason.lower()


# ---------------------------------------------------------------------------
# Test 6: Below min market cap is excluded
# ---------------------------------------------------------------------------


class TestLowMarketCapExclusion:
    """Stocks below min_market_cap are excluded."""

    def test_excludes_below_min_market_cap(self) -> None:
        snapshot = _make_snapshot(market_cap=500_000_000)
        config = MarketScannerConfig(min_market_cap=1_000_000_000)
        result = screen_stock(snapshot, config)
        assert result.passed is False
        assert result.excluded_reason is not None
        assert "market cap" in result.excluded_reason.lower()


# ---------------------------------------------------------------------------
# Test 7: Stock passing all exclusion rules
# ---------------------------------------------------------------------------


class TestPassingStock:
    """A stock meeting all criteria should pass screening."""

    def test_passing_stock_has_passed_true(self) -> None:
        snapshot = _make_snapshot()
        result = screen_stock(snapshot, _default_config())
        assert result.passed is True
        assert result.excluded_reason is None


# ---------------------------------------------------------------------------
# Test 8: Multiple exclusion reasons joined with "; "
# ---------------------------------------------------------------------------


class TestMultipleExclusionReasons:
    """Multiple exclusion reasons are joined with semicolons."""

    def test_multiple_reasons_joined(self) -> None:
        snapshot = _make_snapshot(is_st=True, is_suspended=True)
        result = screen_stock(snapshot, _default_config())
        assert result.passed is False
        assert result.excluded_reason is not None
        reasons = result.excluded_reason.split("; ")
        assert len(reasons) == 2
        assert "ST stock" in result.excluded_reason
        assert "Suspended" in result.excluded_reason


# ---------------------------------------------------------------------------
# Test 9: Passed stock has rank_score > 0 from PE/PB/dividend/drawdown
# ---------------------------------------------------------------------------


class TestRankScorePositive:
    """Passed stocks have rank_score > 0 computed from soft signals."""

    def test_passed_stock_has_positive_rank_score(self) -> None:
        snapshot = _make_snapshot(
            pe_ttm=10.0, pb_ratio=1.0, dividend_yield=0.03, price_vs_52w_high=0.7
        )
        result = screen_stock(snapshot, _default_config())
        assert result.passed is True
        assert result.rank_score > 0.0


# ---------------------------------------------------------------------------
# Test 10: Lower PE produces higher rank_score (inverse relationship)
# ---------------------------------------------------------------------------


class TestPEInverseRelationship:
    """Lower PE should produce a higher rank_score."""

    def test_lower_pe_higher_rank(self) -> None:
        snapshot_low_pe = _make_snapshot(
            pe_ttm=8.0, pb_ratio=2.0, dividend_yield=0.03, price_vs_52w_high=0.8
        )
        snapshot_high_pe = _make_snapshot(
            pe_ttm=40.0, pb_ratio=2.0, dividend_yield=0.03, price_vs_52w_high=0.8
        )
        config = _default_config()
        result_low = screen_stock(snapshot_low_pe, config)
        result_high = screen_stock(snapshot_high_pe, config)
        assert result_low.rank_score > result_high.rank_score


# ---------------------------------------------------------------------------
# Test 11: Higher dividend yield produces higher rank_score
# ---------------------------------------------------------------------------


class TestDividendYieldRelationship:
    """Higher dividend yield should produce higher rank_score."""

    def test_higher_dividend_higher_rank(self) -> None:
        snapshot_low_div = _make_snapshot(
            pe_ttm=15.0, pb_ratio=2.0, dividend_yield=0.01, price_vs_52w_high=0.8
        )
        snapshot_high_div = _make_snapshot(
            pe_ttm=15.0, pb_ratio=2.0, dividend_yield=0.06, price_vs_52w_high=0.8
        )
        config = _default_config()
        result_low = screen_stock(snapshot_low_div, config)
        result_high = screen_stock(snapshot_high_div, config)
        assert result_high.rank_score > result_low.rank_score


# ---------------------------------------------------------------------------
# Test 12: Lower price_vs_52w_high (deeper drawdown) produces higher rank_score
# ---------------------------------------------------------------------------


class TestDrawdownRelationship:
    """Deeper drawdown (lower price_vs_52w_high) should produce higher rank_score."""

    def test_deeper_drawdown_higher_rank(self) -> None:
        snapshot_near_high = _make_snapshot(
            pe_ttm=15.0, pb_ratio=2.0, dividend_yield=0.03, price_vs_52w_high=0.95
        )
        snapshot_deep_dd = _make_snapshot(
            pe_ttm=15.0, pb_ratio=2.0, dividend_yield=0.03, price_vs_52w_high=0.5
        )
        config = _default_config()
        result_near = screen_stock(snapshot_near_high, config)
        result_deep = screen_stock(snapshot_deep_dd, config)
        assert result_deep.rank_score > result_near.rank_score


# ---------------------------------------------------------------------------
# Test 13: None PE/PB handled gracefully
# ---------------------------------------------------------------------------


class TestNonePEPBHandling:
    """None PE/PB should not crash rank calculation."""

    def test_none_pe_pb_no_crash(self) -> None:
        snapshot = _make_snapshot(pe_ttm=None, pb_ratio=None)
        result = screen_stock(snapshot, _default_config())
        assert result.passed is True
        assert result.rank_score >= 0.0

    def test_none_pe_pb_signals_populated(self) -> None:
        snapshot = _make_snapshot(
            pe_ttm=None, pb_ratio=None, dividend_yield=0.05, price_vs_52w_high=0.6
        )
        result = screen_stock(snapshot, _default_config())
        assert result.passed is True
        # Signals dict should still be populated with non-PE/PB values
        assert "dividend" in result.signals
        assert "drawdown" in result.signals


# ---------------------------------------------------------------------------
# Test 14: screen_stocks processes a list of snapshots
# ---------------------------------------------------------------------------


class TestScreenStocksBatch:
    """screen_stocks processes a list of snapshots and returns list of results."""

    def test_batch_screening(self) -> None:
        snapshots = [
            _make_snapshot(ticker="600519.SH"),
            _make_snapshot(ticker="000858.SZ", is_st=True),
            _make_snapshot(ticker="601318.SH"),
        ]
        results = screen_stocks(snapshots, _default_config())
        assert len(results) == 3
        assert all(isinstance(r, ScreeningResult) for r in results)
        tickers = [r.ticker for r in results]
        assert "600519.SH" in tickers
        assert "000858.SZ" in tickers
        assert "601318.SH" in tickers


# ---------------------------------------------------------------------------
# Test 15: rank_screened_stocks sorts by rank_score descending
# ---------------------------------------------------------------------------


class TestRankScreenedStocks:
    """rank_screened_stocks sorts passed stocks by rank_score descending."""

    def test_sorted_by_rank_descending(self) -> None:
        results = [
            ScreeningResult(ticker="A", passed=True, rank_score=10.0),
            ScreeningResult(ticker="B", passed=True, rank_score=50.0),
            ScreeningResult(ticker="C", passed=True, rank_score=30.0),
        ]
        ranked = rank_screened_stocks(results, top_n=10)
        assert [r.ticker for r in ranked] == ["B", "C", "A"]


# ---------------------------------------------------------------------------
# Test 16: rank_screened_stocks respects top_n limit
# ---------------------------------------------------------------------------


class TestRankTopNLimit:
    """rank_screened_stocks respects top_n limit from config."""

    def test_respects_top_n_limit(self) -> None:
        results = [
            ScreeningResult(ticker=f"T{i}", passed=True, rank_score=float(i))
            for i in range(20)
        ]
        ranked = rank_screened_stocks(results, top_n=5)
        assert len(ranked) == 5

    def test_excludes_failed_stocks(self) -> None:
        results = [
            ScreeningResult(ticker="PASS1", passed=True, rank_score=50.0),
            ScreeningResult(
                ticker="FAIL1", passed=False, excluded_reason="ST stock", rank_score=0.0
            ),
            ScreeningResult(ticker="PASS2", passed=True, rank_score=30.0),
        ]
        ranked = rank_screened_stocks(results, top_n=10)
        assert len(ranked) == 2
        assert all(r.passed for r in ranked)
        assert ranked[0].ticker == "PASS1"
        assert ranked[1].ticker == "PASS2"


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


class TestComputeRankScoreDetails:
    """Test _compute_rank_score internal function directly."""

    def test_all_signals_contribute(self) -> None:
        snapshot = _make_snapshot(
            pe_ttm=10.0,
            pb_ratio=1.0,
            dividend_yield=0.04,
            price_vs_52w_high=0.5,
        )
        score, signals = _compute_rank_score(snapshot)
        assert score > 0.0
        assert "pe" in signals
        assert "pb" in signals
        assert "dividend" in signals
        assert "drawdown" in signals

    def test_zero_pe_contribution(self) -> None:
        """PE of 0 or negative contributes 0 to rank score."""
        snapshot = _make_snapshot(
            pe_ttm=0.0, pb_ratio=None, dividend_yield=0.0, price_vs_52w_high=1.0
        )
        score, signals = _compute_rank_score(snapshot)
        assert signals["pe"] == 0.0

    def test_negative_pe_contribution(self) -> None:
        """Negative PE contributes 0 to rank score."""
        snapshot = _make_snapshot(
            pe_ttm=-5.0, pb_ratio=None, dividend_yield=0.0, price_vs_52w_high=1.0
        )
        score, signals = _compute_rank_score(snapshot)
        assert signals["pe"] == 0.0

    def test_score_rounded_to_2dp(self) -> None:
        snapshot = _make_snapshot(
            pe_ttm=7.0, pb_ratio=0.3, dividend_yield=0.033, price_vs_52w_high=0.67
        )
        score, _ = _compute_rank_score(snapshot)
        # Verify rounded to 2 decimal places
        assert score == round(score, 2)
