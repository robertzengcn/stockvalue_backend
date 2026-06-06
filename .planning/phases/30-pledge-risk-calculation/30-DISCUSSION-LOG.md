# Phase 30: Pledge Risk Calculation - Discussion Log

**Date:** 2026-06-06
**Phase:** 30 - pledge-risk-calculation
**Mode:** default (interactive)

## Areas Discussed

### 1. Service Architecture

| Question | Options Presented | User Selection |
|----------|-------------------|----------------|
| Where should pledge risk logic live? | Separate service / Extend RiskAnalyzer / Pure functions | Separate service (Recommended) |
| Single analyze() or multiple methods? | Single analyze() / Multiple granular methods | Single analyze() method |
| Where should result models be defined? | New models in equity_pledge.py / Add to risk.py / Claude discretion | New models in equity_pledge.py |

### 2. Combination Rules Structure

| Question | Options Presented | User Selection |
|----------|-------------------|----------------|
| How should 5 combination rules be structured? | Individual rule functions / Single evaluation function | Individual rule functions (Recommended) |
| Run all rules or short-circuit? | Run all (full audit) / Short-circuit on HIGH | Run all rules (full audit) |

### 3. Controlling Shareholder Edge Cases

| Question | Options Presented | User Selection |
|----------|-------------------|----------------|
| How to handle ties on pledged_to_holding_ratio? | First in list / Highest pledge amount / Graceful skip | First in list (simple) |
| What for zero-pledge stocks (no holders)? | Return LOW with no holder / Return None | Return LOW with no holder (Recommended) |

### 4. Red Flag Format

| Question | Options Presented | User Selection |
|----------|-------------------|----------------|
| Red flag format? | Plain strings / Structured Pydantic objects | Plain strings (Recommended) |

## Decisions Summary

- D-01: Separate PledgeRiskAnalyzer class in pledge_risk_service.py
- D-02: Single analyze() method entry point
- D-03: Result models in equity_pledge.py
- D-04: Individual rule functions for each combination rule
- D-05: All rules evaluated for full audit trail
- D-06: Tie-breaking by first-in-list order
- D-07: Zero-pledge returns LOW with no holder
- D-08: Red flags as plain strings matching existing pattern

## Deferred Ideas

None
