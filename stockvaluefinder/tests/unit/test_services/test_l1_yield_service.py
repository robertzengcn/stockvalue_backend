"""L1 formula verification tests for yield_service pure functions.

Verifies net dividend yield (A-share and HK Stock Connect tax treatment),
yield gap calculation with max(bond, deposit) logic, and yield recommendation
classification at boundary conditions.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.enums import Market, YieldRecommendation
from stockvaluefinder.services.yield_service import (
    calculate_net_dividend_yield,
    calculate_yield_gap,
    determine_yield_recommendation,
)


# ---------------------------------------------------------------------------
# Net dividend yield
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1NetDividendYield:
    """L1 tests for net dividend yield after tax.

    A-shares: 0% tax (gross_yield passes through unchanged).
    HK Stock Connect: 20% withholding tax (gross_yield * 0.80).
    Note: IEEE 754 floating point requires approx for multiplication results.
    """

    def test_a_share_5pct(self) -> None:
        """A-share: gross=0.05 -> net=0.05 (0% tax)."""
        net = calculate_net_dividend_yield(0.05, Market.A_SHARE)
        assert net == 0.05

    def test_hk_share_5pct(self) -> None:
        """HK Stock Connect: gross=0.05 -> net=0.04 (20% tax)."""
        net = calculate_net_dividend_yield(0.05, Market.HK_SHARE)
        assert net == pytest.approx(0.04, abs=1e-10)

    def test_a_share_8pct(self) -> None:
        """A-share: gross=0.08 -> net=0.08."""
        net = calculate_net_dividend_yield(0.08, Market.A_SHARE)
        assert net == 0.08

    def test_hk_share_10pct(self) -> None:
        """HK: gross=0.10 -> net=0.08 (20% tax)."""
        net = calculate_net_dividend_yield(0.10, Market.HK_SHARE)
        assert net == pytest.approx(0.08, abs=1e-10)


# ---------------------------------------------------------------------------
# Yield gap
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1YieldGap:
    """L1 tests for yield gap calculation.

    Formula: yield_gap = net_yield - max(bond, deposit)
    Pure arithmetic -- direct equality assertions.
    """

    def test_yield_gap_bond_dominant(self) -> None:
        """net=0.05, bond=0.03, deposit=0.025 -> gap = 0.05 - max(0.03, 0.025) = 0.02."""
        gap = calculate_yield_gap(0.05, 0.03, 0.025)
        assert gap == pytest.approx(0.02, abs=1e-10)

    def test_yield_gap_deposit_dominant(self) -> None:
        """net=0.02, bond=0.03, deposit=0.04 -> gap = 0.02 - 0.04 = -0.02."""
        gap = calculate_yield_gap(0.02, 0.03, 0.04)
        assert gap == pytest.approx(-0.02, abs=1e-10)

    def test_yield_gap_equal_rates(self) -> None:
        """net=0.03, bond=0.03, deposit=0.03 -> gap = 0.0."""
        gap = calculate_yield_gap(0.03, 0.03, 0.03)
        assert gap == pytest.approx(0.0, abs=1e-10)


# ---------------------------------------------------------------------------
# Yield recommendation
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1YieldRecommendation:
    """L1 tests for yield recommendation classification.

    Thresholds:
    - ATTRACTIVE: yield_gap > 0.02 (strict >)
    - NEUTRAL: -0.01 <= yield_gap <= 0.02
    - UNATTRACTIVE: yield_gap < -0.01

    Source code uses strict > for ATTRACTIVE and >= for NEUTRAL lower bound.
    """

    def test_attractive(self) -> None:
        """gap=0.025 > 0.02 -> ATTRACTIVE."""
        rec = determine_yield_recommendation(0.025)
        assert rec == YieldRecommendation.ATTRACTIVE

    def test_neutral(self) -> None:
        """gap=0.01 (-1% to 2%) -> NEUTRAL."""
        rec = determine_yield_recommendation(0.01)
        assert rec == YieldRecommendation.NEUTRAL

    def test_unattractive(self) -> None:
        """gap=-0.015 (< -1%) -> UNATTRACTIVE."""
        rec = determine_yield_recommendation(-0.015)
        assert rec == YieldRecommendation.UNATTRACTIVE

    def test_boundary_just_above_attractive(self) -> None:
        """gap=0.0201 (just above 0.02, strict > satisfied) -> ATTRACTIVE."""
        rec = determine_yield_recommendation(0.0201)
        assert rec == YieldRecommendation.ATTRACTIVE

    def test_boundary_exactly_at_002(self) -> None:
        """gap=0.02 (exactly at boundary, strict > NOT satisfied) -> NEUTRAL."""
        rec = determine_yield_recommendation(0.02)
        assert rec == YieldRecommendation.NEUTRAL

    def test_boundary_exactly_at_neg001(self) -> None:
        """gap=-0.01 (exactly at -1% boundary, >= -0.01 satisfied) -> NEUTRAL."""
        rec = determine_yield_recommendation(-0.01)
        assert rec == YieldRecommendation.NEUTRAL
