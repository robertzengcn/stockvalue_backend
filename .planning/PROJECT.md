# StockValueFinder

## What This Is

An AI-enhanced value investment decision platform for individual investors analyzing A-share and Hong Kong stocks. The system performs automated financial fraud detection (Beneish M-Score, Piotroski F-Score), dynamic DCF valuation with live risk-free rates, dividend yield gap analysis, and RAG-powered annual report retrieval. LLM-powered narratives explain analysis results in plain Chinese.

## Core Value

Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## Requirements

### Validated

- ✓ Risk analysis API (M-Score, F-Score, 存贷双高 detection, profit-cash divergence) — existing
- ✓ DCF valuation API (2-stage growth model, WACC, terminal value, margin of safety) — existing
- ✓ Yield gap analysis API (tax-aware dividend yield vs risk-free rates) — existing
- ✓ Multi-source data fetching (AKShare → efinance → Tushare fallback chain) — existing
- ✓ LLM narrative generation (DeepSeek with graceful fallback) — existing
- ✓ Analysis persistence (PostgreSQL with 7 ORM models, Alembic migrations) — existing
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
- ✓ ROIC-WACC spread analysis (NOPAT / invested capital, true WACC with debt weighting, spread trend, moat detection) — Phase 9
- ✓ ROIC data layer (multi-year AKShare fetch, Redis cache, ROICResultDB ORM, Alembic migration 011) — Phase 9
- ✓ POST /api/v1/analyze/roic endpoint with sector-aware NOPAT and 3-year trend — Phase 9

### Active

- [ ] Capital Allocation scorecard (buyback yield, 5-year DPU stability, blind expansion alerts when ROIC < WACC + CapEx surge)
- [ ] Policy Resonance Engine (upload policy docs → RAG vector matching → auto-adjust DCF terminal growth rate)
- [ ] Composite Alpha score with fixed weights (40% ROIC-WACC, 30% Capital Allocation, 20% Policy, 10% Moat trend)
- [ ] Extend AKShare/efinance client for buyback data (stock_repurchase_em) and CapEx growth — Phase 10

### Out of Scope

- Docker-based calculation sandbox — subprocess sandbox sufficient for MVP
- All A-share + HK stock universe — CSI 300 constituents only for this milestone
- Interactive chat interface — batch static reports sufficient for MVP
- User authentication — single-user system for now
- Frontend application — API-only for this milestone
- Real-time WebSocket updates — SSE sufficient for status push
- HKMA live rate fetching — static HK rates acceptable
- Batch report generation for all CSI 300 — individual stock analysis first
- Celery + RabbitMQ — Arq + Redis sufficient for current task volume
- HK stock (HKEX 披露易) monitoring — A-share first, HK in future milestone
- OCR (PaddleOCR) — PyMuPDF text extraction first, OCR as fallback in future phase
- Playwright browser automation — API/HTTP preferred, browser automation only as last resort
- Supply chain / customer dependency monitoring (P2) — data quality issues (A-share top-5 client names often hidden), deferred to future milestone
- Live policy news crawling — upload-based RAG matching sufficient for v1.2
- User-adjustable Alpha weights — fixed weights sufficient for MVP

## Context

## Current Milestone: v1.2 Alpha Engine V2.0

**Goal:** Shift from "historical audit" to "forward-looking value prediction" by quantifying value creation (ROIC-WACC), capital efficiency, policy alignment, and composite Alpha scoring.

**Target features:**
- ROIC-WACC spread analysis with 3-year moat trend detection
- Capital Allocation scorecard (buyback yield, dividend stability, blind expansion alerts)
- Policy Resonance Engine (upload policy docs → RAG matching → auto-adjust DCF parameters)
- Composite Alpha score with fixed weights (40% ROIC-WACC, 30% Capital Allocation, 20% Policy, 10% Moat)

### Current Codebase State
- **FastAPI backend** with 3 analysis APIs (risk, valuation, yield) and RAG document pipeline
- **24,057 LOC Python** (9,885 app + 14,172 test)
- **100+ tests** with 80%+ coverage including PostgreSQL-backed E2E integration tests
- **Redis caching** integrated across all external data routes with graceful degradation
- **RAG pipeline** with PDF processing, bge-m3 embeddings, Qdrant vector search
- **9 ORM models**, 11 Alembic migrations, document persistence layer
- **Tech stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic 2, PostgreSQL, Redis, Qdrant, LangChain/LangGraph

### Key Technical Debt
- Agent module (coordinator, risk, valuation, yield) is scaffolding only — needs LangGraph implementation
- Calculation sandbox is a TODO stub
- Database credentials hardcoded in db/base.py (security issue)
- AKShare field name stability is uncontrolled — pin version and validate schemas
- FCF CapEx sign convention differs between data sources — normalize in client layer
- Some RAG defaults are hardcoded (can be made configurable later)

### Architecture Pattern
- **Deterministic agent architecture**: LLMs handle understanding/narrative, Python performs exact calculations
- **Layered architecture**: API → Service → Repository → External/DB
- **Pure function services**: All calculations are stateless pure functions
- **Graceful degradation**: LLM narratives return None on failure, Redis/Qdrant degrade gracefully
- **RAG pattern**: Parent-child chunking (500/2000 tokens), vector search + metadata filtering

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
| API/HTTP over Playwright for data fetching | More stable, testable, lower operational cost than browser automation | ✓ Good |
| CSI 300 only for MVP | Original plan from PRD, manageable scope for validation | ✓ Good |
| Full RAG with PDF processing | Annual reports are primary analysis source, need semantic search | ✓ Good |
| Multi-agent over single agent | Parallel analysis of risk/valuation/yield is more efficient | — Pending |
| DeepSeek as LLM provider | Cost-effective, strong Chinese language support | ✓ Good |
| Free data sources (AKShare/efinance) | No API key management, no cost for MVP | ✓ Good |
| Audit trail with frozen Pydantic models | Immutable audit data, per-index traceability | ✓ Good |
| Redis graceful degradation | System works without Redis, cache is optimization not dependency | ✓ Good |
| Parent context from Qdrant (not PostgreSQL) | Simpler MVP retriever, single source of truth for vectors | ✓ Good |
| Async PDF processing with BackgroundTasks | Upload returns immediately, processing happens in background | ✓ Good |
| skip_if_no_db pytest marker | Integration tests skip gracefully when no DB available | ✓ Good |
| Document context in ApiResponse meta field | Avoids breaking existing response schemas | ✓ Good |
| Fixed weights for Alpha composite score | Simple, transparent, auditable — no user configuration needed yet | — Pending (v1.2) |
| Policy upload + RAG matching (no live crawling) | Leverages existing Qdrant infrastructure, user-controlled input | — Pending (v1.2) |
| 3-year ROIC-WACC trend for moat detection | Academic backing: persistent spread widening signals competitive advantage | ✓ Phase 9 |
| AKShare/efinance for ROIC inputs | Consistent with existing data pipeline, free, no new infrastructure | ✓ Phase 9 |
| Dual NOPAT formula (financial vs non-financial) | Banks/insurance/securities use interest-income NOPAT, not operating profit | ✓ Phase 9 |
| scipy for trend line regression | Lightweight, well-tested, only new dependency for 3-year slope calculation | ✓ Phase 9 |
| Non-blocking DB persistence in API routes | Return result even if DB save fails — analysis result is primary, persistence is secondary | ✓ Phase 9 |

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

---
*Last updated: 2026-05-05 after Phase 9 completion*
