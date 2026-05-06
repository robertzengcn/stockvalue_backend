# Phase 11: Policy Resonance Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 11-Policy Resonance Engine
**Areas discussed:** Stock-business-to-policy matching strategy, Resonance scoring formula (0-100), DCF auto-adjustment rules, Policy document metadata & search UX

---

## Stock-Business-to-Policy Matching Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| AKShare field | stock_individual_info_em() with 经营范围/主营业务, add business_description to StockDB | ✓ |
| Extract from RAG annual reports | Query existing Qdrant for MD&A section content per ticker | |
| User-provided text | User passes business description text when requesting analysis | |

| Option | Description | Selected |
|--------|-------------|----------|
| Top 3 matches | Standard coverage, less noise | |
| Top 5 matches | Broader coverage for multi-domain policies | ✓ |
| Top 1 match only | Max precision, may miss multi-domain | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, LLM classification | DeepSeek verifies matches, reduces false positives per POL-02 | ✓ |
| No, vector similarity only | Faster but more false positives | |
| Conditional (0.6-0.8 range) | Only verify ambiguous matches | |

**User's choice:** AKShare for business descriptions, top 5 matches, LLM verification
**Notes:** User selected all recommended options — AKShare field most reliable for CSI 300, top 5 for broader policy coverage

---

## Resonance Scoring Formula (0-100)

| Option | Description | Selected |
|--------|-------------|----------|
| Weighted formula | 60% cosine similarity + 40% LLM confidence | ✓ |
| Direct cosine * 100 | Simple but ignores LLM verification | |
| Tiered bands (80/50/20) | Clear qualitative categories, less granular | |

| Option | Description | Selected |
|--------|-------------|----------|
| Confidence + relevance | LLM returns {relevant, confidence, reason} | ✓ |
| Binary relevant/not relevant | Simpler prompt, no gradation | |

| Option | Description | Selected |
|--------|-------------|----------|
| 40/100 threshold | Reasonable with weighted formula | ✓ |
| 50/100 threshold | Higher bar, more conservative | |
| You decide | Claude determines threshold | |

**User's choice:** Weighted formula with LLM confidence, structured verdict, 40/100 threshold
**Notes:** Weighted formula uses both signal types. 40/100 threshold set for DCF eligibility.

---

## DCF Auto-Adjustment Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered: +1.5% / +1.0% / 0% | 3 tiers by resonance score, no negative adjustment | ✓ |
| Binary: +1% / 0% | Matches ROADMAP spec exactly, simplest | |
| Proportional to score | Linear scaling, most granular but harder to explain | |

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at +1.5% | Matches max tier, subject to existing MAX_TERMINAL_GROWTH | ✓ |
| Cap at +2.0% | More aggressive sensitivity | |
| You decide | Claude determines cap | |

| Option | Description | Selected |
|--------|-------------|----------|
| Combined in one response | Score + DCF adjustment in single API call | ✓ |
| Separate endpoints | More modular but requires two calls | |

**User's choice:** Tiered adjustment, +1.5% cap, combined response
**Notes:** No negative adjustment (restrictive policies hard to detect). Combined response avoids extra round-trips.

---

## Policy Document Metadata & Search UX

| Option | Description | Selected |
|--------|-------------|----------|
| Enriched + LLM extraction | title, policy_type, issuing_body, effective_date, industry_tags; LLM auto-extracts | ✓ |
| Minimal (title, date, type) | User provides at upload, simpler | |
| You decide | Claude determines fields | |

| Option | Description | Selected |
|--------|-------------|----------|
| Match all policies | Upload once, applies to all stocks automatically | ✓ |
| User-selects per request | More control but UX friction | |

| Option | Description | Selected |
|--------|-------------|----------|
| Separate collection | policy_documents with own indexes, different schema | ✓ |
| Same collection | report_type='policy' in annual_reports | |

**User's choice:** Enriched metadata with LLM extraction, match all policies, separate collection
**Notes:** Separate collection per ROADMAP decision. LLM extraction during upload reduces user friction.

---

## Claude's Discretion

- Exact AKShare method name and field mapping for business descriptions
- Policy upload API endpoint path and request/response models
- New ORM model field names and Alembic migration details
- LLM prompt engineering for match verification and metadata extraction
- Internal function organization within policy_service.py
- Test file structure and test case selection

## Deferred Ideas

None — discussion stayed within phase scope.
