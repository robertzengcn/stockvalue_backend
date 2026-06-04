---
phase: 26
phase_slug: screening-scoring-engine
created: 2026-06-04
status: active
---

# Validation Strategy: Phase 26 - Screening & Scoring Engine

## Test-to-Requirement Mapping

| Requirement | Test File | Test Coverage |
|-------------|-----------|---------------|
| SCR-01 (Coarse Screening) | tests/unit/test_market_scanner/test_coarse_screener.py | ST/suspended/missing/liquidity/OCF filters + priority sorting |
| SCR-05 (Composite Scoring) | tests/unit/test_market_scanner/test_composite_scorer.py | 5-dimension normalization + weighted sum + threshold filtering |
| SCR-06 (Reason Generation) | tests/unit/test_market_scanner/test_reason_generator.py | Selection reasons + risk flags + minimum 1 risk flag per candidate |
| SCR-07 (Configurable Weights) | tests/unit/test_market_scanner/test_config.py | ScoringWeightsConfig validation + MarketScannerConfig extension |

## Verification Dimensions

1. **Formula correctness**: Each filter, normalization, and scoring formula tested with known inputs/outputs
2. **Edge cases**: Zero/negative values, missing data, all-pass/all-fail scenarios
3. **Boundary conditions**: Score at exactly threshold (0.0, 1.0, min_composite_score)
4. **Immutability**: All configs frozen, all functions pure (no side effects)
5. **Compliance**: Every candidate has at least 1 risk flag (even passing stocks)
6. **Weight sum**: ScoringWeightsConfig validates sum ≈ 1.0 (within epsilon)

## Sampling Strategy

Continuous — every task has automated `<verify>` commands via `uv run pytest`.
