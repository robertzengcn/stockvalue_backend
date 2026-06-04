"""Coarse screening engine for the Market Index Value Scanner.

This module provides pure functions for hard-exclusion screening and
soft-prioritization ranking of stocks. It operates on ScreeningSnapshot
data populated by the scan orchestrator (Phase 27) and uses thresholds
from MarketScannerConfig.

Functions:
    - screen_stock: Apply hard-exclusion rules to a single stock
    - screen_stocks: Batch screening over multiple stocks
    - rank_screened_stocks: Sort passed stocks by rank_score, limit to top_n
    - _compute_rank_score: Private helper for soft prioritization signals

All functions are stateless pure functions with no I/O side effects.
"""

from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import ScreeningResult, ScreeningSnapshot


def _compute_rank_score(
    snapshot: ScreeningSnapshot,
) -> tuple[float, dict[str, float]]:
    """Compute a prioritization score from soft signals.

    Only called for stocks that passed all hard-exclusion rules.
    The rank score combines four signals:
        - PE signal: lower PE = higher score (inverse)
        - PB signal: lower PB = higher score (inverse)
        - Dividend signal: higher yield = higher score
        - Drawdown signal: deeper drawdown = higher score

    Args:
        snapshot: Market data snapshot for the stock.

    Returns:
        Tuple of (rank_score, signals_dict) where rank_score is rounded
        to 2 decimal places and signals_dict contains individual signal
        values for transparency.
    """
    # PE signal: inverse relationship, lower PE = higher score
    if snapshot.pe_ttm is not None and snapshot.pe_ttm > 0:
        pe_signal = 50.0 / max(snapshot.pe_ttm, 1.0)
    else:
        pe_signal = 0.0

    # PB signal: inverse relationship, lower PB = higher score
    if snapshot.pb_ratio is not None and snapshot.pb_ratio > 0:
        pb_signal = 30.0 / max(snapshot.pb_ratio, 0.1)
    else:
        pb_signal = 0.0

    # Dividend signal: higher yield = higher score
    dividend_signal = snapshot.dividend_yield * 100.0

    # Drawdown signal: deeper drawdown = higher score
    drawdown_signal = (1.0 - snapshot.price_vs_52w_high) * 50.0

    signals: dict[str, float] = {
        "pe": round(pe_signal, 2),
        "pb": round(pb_signal, 2),
        "dividend": round(dividend_signal, 2),
        "drawdown": round(drawdown_signal, 2),
    }

    total = pe_signal + pb_signal + dividend_signal + drawdown_signal
    return round(total, 2), signals


def screen_stock(
    snapshot: ScreeningSnapshot,
    config: MarketScannerConfig,
) -> ScreeningResult:
    """Apply hard-exclusion rules and compute prioritization for a single stock.

    Exclusion rules are evaluated in order:
        1. ST status -> "ST stock"
        2. Suspended -> "Suspended"
        3. Missing price data -> "Missing price data"
        4. Low turnover ratio -> "Below minimum liquidity"
        5. Insufficient OCF years -> "Persistently negative operating cash flow"
        6. Below min market cap -> "Below minimum market cap"

    If any exclusion is triggered, the stock fails with all reasons joined
    by "; ". If no exclusions, rank_score is computed from soft signals.

    Args:
        snapshot: Market data snapshot for the stock.
        config: Scanner configuration with thresholds.

    Returns:
        ScreeningResult with pass/fail status, exclusion reasons, and rank score.
    """
    reasons: list[str] = []

    # Hard exclusion rules in order
    if snapshot.is_st:
        reasons.append("ST stock")
    if snapshot.is_suspended:
        reasons.append("Suspended")
    if not snapshot.has_price_data:
        reasons.append("Missing price data")
    if snapshot.turnover_ratio < config.min_turnover_ratio:
        reasons.append("Below minimum liquidity")
    if snapshot.ocf_positive_years < config.min_ocf_positive_years:
        reasons.append("Persistently negative operating cash flow")
    if snapshot.market_cap < config.min_market_cap:
        reasons.append("Below minimum market cap")

    if reasons:
        return ScreeningResult(
            ticker=snapshot.ticker,
            passed=False,
            excluded_reason="; ".join(reasons),
            rank_score=0.0,
            signals={},
        )

    # Passed all exclusions -- compute rank score from soft signals
    rank_score, signals = _compute_rank_score(snapshot)

    return ScreeningResult(
        ticker=snapshot.ticker,
        passed=True,
        excluded_reason=None,
        rank_score=rank_score,
        signals=signals,
    )


def screen_stocks(
    snapshots: list[ScreeningSnapshot],
    config: MarketScannerConfig,
) -> list[ScreeningResult]:
    """Apply screen_stock to each snapshot in a batch.

    Args:
        snapshots: List of market data snapshots to screen.
        config: Scanner configuration with thresholds.

    Returns:
        List of ScreeningResult objects, one per input snapshot.
    """
    return [screen_stock(snapshot, config) for snapshot in snapshots]


def rank_screened_stocks(
    results: list[ScreeningResult],
    top_n: int,
) -> list[ScreeningResult]:
    """Filter to passed results, sort by rank_score descending, limit to top_n.

    Args:
        results: List of screening results from screen_stock or screen_stocks.
        top_n: Maximum number of stocks to return.

    Returns:
        Top N passed stocks sorted by rank_score descending.
    """
    passed = [r for r in results if r.passed]
    sorted_results = sorted(passed, key=lambda r: r.rank_score, reverse=True)
    return sorted_results[:top_n]
