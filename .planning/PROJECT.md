# StockValueFinder

## What This Is

An AI-enhanced value investment decision platform for individual investors analyzing A-share and Hong Kong stocks. The system performs automated financial fraud detection (Beneish M-Score, Piotroski F-Score), dynamic DCF valuation with live risk-free rates, dividend yield gap analysis, forward-looking Alpha scoring (ROIC-WACC, Capital Allocation, Policy Resonance), and RAG-powered annual report retrieval. LLM-powered narratives explain analysis results in plain Chinese.

## Core Value

Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## Requirements

### Validated

- ✓ Risk analysis API (M-Score, F-Score, 存贷双高 detection, profit-cash divergence) — existing
- ✓ DCF valuation API (2-stage growth model, WACC, terminal value, margin of safety) — existing
- ✓ Yield gap analysis API (tax-aware dividend yield vs risk-free rates) — existing
- ✓ Multi-source data fetching (AKShare → efinance → Tushare fallback chain) — existing
- ✓ LLM narrative generation (DeepSeek with graceful fallback) — existing
- ✓ User registration (open registration with email + password) — v1.3
- ✓ JWT authentication (login, refresh, logout) — v1.3
- ✓ Role-based access control (Admin + User) — v1.3
- ✓ Admin user management API (CRUD, role assignment, enable/disable) — v1.3
- ✓ Per-user access control (stock/API restrictions) — v1.3
- ✓ Usage analytics (API call counts, analysis usage, error rates per user) — v1.3
- ✓ Per-user rate limiting — v1.3
- ✓ Auth middleware protecting all existing analysis endpoints — v1.3
- ✓ Standardized API envelope (ApiResponse[T] with error handling) — existing
- ✓ Interest rate fetching (live China 10Y treasury via AKShare, static deposit rates) — existing
- ✓ M-Score real calculation from financial data with 8 computed indices and audit trail — v1.0
- ✓ Redis caching for all external data methods (24h financials, 5min prices, 1h rates) — v1.0
- ✓ Comprehensive test suite (100+ tests, 80%+ coverage, E2E integration tests) — v1.0
- ✓ RAG pipeline (PDF upload → chunking → bge-m3 embeddings → Qdrant → retrieval) — v1.0
- ✓ Smart Watcher for A-share announcement monitoring (巨潮/交易所) — v1.1
- ✓ Processing pipeline: download → parse → analyze → update RAG — v1.1
- ✓ State machine: PENDING → DOWNLOADING → PARSING → ANALYZING → DONE/FAILED — v1.1
- ✓ Task management with deduplication (source ID + SHA256 + business key) — v1.1
- ✓ SSE notification on analysis completion — v1.1
- ✓ Subprocess-based calculation sandbox — v1.1
- ✓ ROIC-WACC spread analysis (NOPAT / invested capital, true WACC with debt weighting, spread trend, moat detection) — v1.2
- ✓ Capital Allocation scorecard (buyback yield, DPU stability, blind expansion alerts, combined A/B/C/D grade) — v1.2
- ✓ Policy Resonance Engine (PDF upload, RAG matching, DCF terminal growth auto-adjustment) — v1.2
- ✓ Composite Alpha score with fixed weights (40% ROIC-WACC, 30% CapEx, 20% Policy, 10% Moat) — v1.2
- ✓ POST /api/v1/analyze/alpha endpoint with full audit trail and live orchestration — v1.2
- ✓ Metric Registry (YAML-based single source of truth for all metrics) — v1.4
- ✓ Golden Dataset (14 CSI 300 stocks with computed golden values) — v1.4
- ✓ L1 Formula Verification (161 tests for all pure calculation functions) — v1.4
- ✓ L2 Field Mapping Verification (403 tests for AKShare/efinance field extraction) — v1.4
- ✓ L3 End-to-End Golden Testing (22 tests, full pipeline validation) — v1.4
- ✓ Reconcile CLI tool (compare computed vs expected for any ticker+year) — v1.4
- ✓ CI integration with golden test markers and GitHub Actions — v1.4

### Active

- Index constituent sync (CSI 300 + CSI 500, with history tracking and dedup)
- Market coarse screening (filter ST, suspended, low liquidity, missing data)
- DCF-based value confirmation with configurable safety margin thresholds
- Quality and risk review layer (ROIC-WACC, M-Score, cash flow divergence, leverage)
- Composite scoring engine with configurable weights and normalization
- Structured candidate reasons and risk flag generation (deterministic)
- Scan run tracking (daily light, weekly deep, event-triggered, manual)
- Market Scanner REST API (runs, candidates, watchlist integration)
- arq worker integration for scheduled scans
- Reuse existing analysis services (DCF, Risk, Yield, Alpha)

### Out of Scope

- Docker-based calculation sandbox — subprocess sandbox sufficient for MVP
- All A-share + HK stock universe — CSI 300 constituents only for this milestone
- Interactive chat interface — batch static reports sufficient for MVP
- User authentication — single-user system for now (v1.3 adds auth)
- Frontend application — API-only for this milestone
- Real-time WebSocket updates — SSE sufficient for status push
- HKMA live rate fetching — static HK rates acceptable
- Batch report generation for all CSI 300 — individual stock analysis first
- Celery + RabbitMQ — Arq + Redis sufficient for current task volume
- HK stock (HKEX 披露易) monitoring — A-share first, HK in future milestone
- OCR (PaddleOCR) — PyMuPDF text extraction first, OCR as fallback in future phase
- Playwright browser automation — API/HTTP preferred, browser automation only as last resort
- Supply chain / customer dependency monitoring — data quality issues, deferred to future milestone
- Live policy news crawling — upload-based RAG matching sufficient
- User-adjustable Alpha weights — fixed weights sufficient for MVP
- Sector-relative ROIC ranking — requires peer group definitions, deferred
- Frontend candidate pool page — backend API only in v1.5, frontend in future milestone
- Full A-share/HK stock universe scanning — CSI 300 + CSI 500 only in V1
- User-adjustable scanner weights — fixed weights sufficient for V1
- Intraday real-time scanning — post-market close scanning only in V1
- Custom user stock pools — index pools only in V1
- Industry theme index support — CSI 300 + CSI 500 only in V1

## Context

### Current Codebase State
- **FastAPI backend** with 7 analysis APIs (risk, valuation, yield, roic, capex, policy, alpha) and RAG document pipeline
- **44,380 LOC Python** (21,054 app + 23,326 test)
- **997+ unit tests** with 80%+ coverage, PostgreSQL-backed E2E integration tests
- **Redis caching** integrated across all external data routes with graceful degradation
- **RAG pipeline** with PDF processing, bge-m3 embeddings, Qdrant vector search
- **14 ORM models**, 14 Alembic migrations (through 014_alpha_scores_table)
- **Tech stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic 2, PostgreSQL, Redis, Qdrant, scipy, LangChain/LangGraph

### Key Technical Debt
- Agent module (coordinator, risk, valuation, yield) is scaffolding only — needs LangGraph implementation
- Calculation sandbox is a TODO stub
- Database credentials hardcoded in db/base.py (security issue)
- AKShare field name stability is uncontrolled — pin version and validate schemas
- FCF CapEx sign convention differs between data sources — normalize in client layer
- Some RAG defaults are hardcoded (can be made configurable later)
- LLM prompt for DCF parameter extraction from policy text needs iterative testing
- AKShare stock_repurchase_em() data quality varies — cached with 24h TTL

### Architecture Pattern
- **Deterministic agent architecture**: LLMs handle understanding/narrative, Python performs exact calculations
- **Layered architecture**: API → Service → Repository → External/DB
- **Pure function services**: All calculations are stateless pure functions
- **Graceful degradation**: LLM narratives return None on failure, Redis/Qdrant degrade gracefully
- **RAG pattern**: Parent-child chunking (500/2000 tokens), vector search + metadata filtering
- **Orchestration endpoints**: Direct route handler function calls (not HTTP self-call) for composable analysis
- **Non-blocking persistence**: DB errors logged but API response still returned

## Constraints

- **Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, PostgreSQL — established, must keep
- **Data Sources**: AKShare + efinance (free, no API key) as primary — Tushare as optional fallback
- **Stock Universe**: CSI 300 constituents only for this milestone
- **LLM**: DeepSeek as primary provider (cost-effective for Chinese language generation)
- **Vector DB**: Qdrant (Docker-based, integrated in v1.0)
- **Language**: Chinese for user-facing narratives, English for code/internal

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Subprocess sandbox over Docker | Simpler implementation, sufficient isolation for MVP | ✓ Good |
| Arq + Redis over Celery + RabbitMQ | Lighter weight, asyncio-friendly, sufficient for current task volume | ✓ Good |
| APScheduler for scheduling | Mature, simple cron-like scheduling, no additional infrastructure | ✓ Good |
| PyMuPDF first, OCR as fallback | Fast text extraction handles most PDFs, OCR only for scanned documents | ✓ Good |
| A-share first, HK later | Reduce scope complexity, validate pipeline with single market first | ✓ Good |
| API/HTTP over Playwright for data fetching | More stable, testable, lower operational cost | ✓ Good |
| CSI 300 only for MVP | Original plan from PRD, manageable scope for validation | ✓ Good |
| Full RAG with PDF processing | Annual reports are primary analysis source, need semantic search | ✓ Good |
| DeepSeek as LLM provider | Cost-effective, strong Chinese language support | ✓ Good |
| Free data sources (AKShare/efinance) | No API key management, no cost for MVP | ✓ Good |
| Audit trail with frozen Pydantic models | Immutable audit data, per-index traceability | ✓ Good |
| Redis graceful degradation | System works without Redis, cache is optimization not dependency | ✓ Good |
| Fixed weights for Alpha composite score (40/30/20/10) | Simple, transparent, auditable — no user configuration needed | ✓ Good |
| Policy upload + RAG matching (no live crawling) | Leverages existing Qdrant infrastructure, user-controlled input | ✓ Good |
| 3-year ROIC-WACC trend for moat detection | Academic backing: persistent spread widening signals competitive advantage | ✓ Good |
| Dual NOPAT formula (financial vs non-financial) | Banks/insurance/securities use interest-income NOPAT | ✓ Good |
| scipy for trend line regression | Lightweight, well-tested, only new dependency | ✓ Good |
| Non-blocking DB persistence in API routes | Analysis result is primary, persistence is secondary | ✓ Good |
| Direct route handler function calls for orchestration | Avoids HTTP self-call overhead and ASGI deadlock risk | ✓ Good |
| stock_profile_cninfo for business descriptions | stock_individual_info_em does NOT return business descriptions (verified) | ✓ Good |
| Policy documents in separate Qdrant collection | Different metadata schema from annual reports | ✓ Good |
| IEEE 754 fix with round(..., 2) in normalization | Floating point precision caused test failures | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current Milestone: v1.5 Market Index Value Scanner

**Goal:** Build a systematic scanner that automatically discovers undervalued stocks across CSI 300 and CSI 500 index pools using a 3-layer screening funnel (market coarse screen → value confirmation → quality/risk review).

**Target features:**
- Index constituent sync (CSI 300 + CSI 500 with history tracking)
- 3-layer screening funnel with configurable thresholds
- Composite scoring (safety margin 35%, Alpha 25%, risk penalty 20%, yield gap 10%, valuation percentile 10%)
- Structured candidate reasons and risk flags (deterministic, LLM optional for narrative)
- Scan run tracking (daily light + weekly deep + manual trigger)
- Market Scanner REST API (runs, candidates, watchlist integration)
- arq worker integration (cron jobs for scheduled scans)
- Reuse existing DCF, Risk, Yield, Alpha analysis services

---
*Last updated: 2026-06-04 after v1.5 milestone initiation*
