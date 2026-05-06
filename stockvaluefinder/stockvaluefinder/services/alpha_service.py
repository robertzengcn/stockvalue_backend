"""Alpha composite score pure calculation functions.

Placeholder stubs for TDD RED phase - implementations follow in GREEN phase.
"""

from stockvaluefinder.models.capital_allocation import CapitalAllocationGrade
from stockvaluefinder.models.enums import AlphaLevel
from stockvaluefinder.models.roic import MoatTrend


def normalize_roic_wacc_score(spread: float | None) -> float:
    """Map ROIC-WACC spread to 0-100 using linear clamp +/-10% (D-02)."""
    raise NotImplementedError("TDD RED stub")


def normalize_capex_score(grade: CapitalAllocationGrade) -> float:
    """Map capital allocation grade A/B/C/D to 100/75/50/25 (D-03)."""
    raise NotImplementedError("TDD RED stub")


def normalize_policy_score(score: float) -> float:
    """Pass-through with safety clamp for policy resonance score (0-100)."""
    raise NotImplementedError("TDD RED stub")


def normalize_moat_score(trend: MoatTrend | None) -> float:
    """Map moat trend to score (D-04): COMPETITIVE_ADVANTAGE=100, STABLE=50, else 0."""
    raise NotImplementedError("TDD RED stub")


def calculate_alpha_score(
    roic_wacc_score: float,
    capex_score: float,
    policy_score: float,
    moat_score: float,
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10),
) -> float:
    """Calculate weighted composite Alpha score."""
    raise NotImplementedError("TDD RED stub")


def classify_alpha_level(score: float) -> AlphaLevel:
    """Classify Alpha score into tier: EXCELLENT/GOOD/FAIR/WEAK/POOR."""
    raise NotImplementedError("TDD RED stub")
