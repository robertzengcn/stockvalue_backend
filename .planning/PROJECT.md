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

### Active

- [ ] Smart Watcher: Automated monitoring of A-share (巨潮/交易所) financial report announcements with configurable polling frequency
- [ ] Processing Pipeline: Download PDF → Parse/structure → Trigger AI analysis (M-Score/F-Score/DCF) → Update RAG vector store
- [ ] State Machine: PENDING → DOWNLOADING → PARSING → ANALYZING → DONE/FAILED with retry and idempotent processing
- [ ] Task Management: Status tracking, deduplication (source ID + SHA256 + business key), summary vs full-text handling
- [ ] Notification: Analysis completion awareness (SSE or async push when pipeline finishes)
- [ ] Subprocess-based calculation sandbox (resource-limited Python execution)

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

## Context

## Current Milestone: v1.1 Smart Financial Report Pipeline

**Goal:** Build an event-driven pipeline that automatically monitors, downloads, parses, and processes A-share financial reports, ensuring the AI analysis engine stays current without manual data collection.

**Target features:**
- Smart Watcher for A-share announcement monitoring
- Processing pipeline: download → parse → analyze → update RAG
- State machine with retry and idempotent processing
- Task management with deduplication
- Analysis completion notification

### Current Codebase State
- **FastAPI backend** with 3 analysis APIs (risk, valuation, yield) and RAG document pipeline
- **24,057 LOC Python** (9,885 app + 14,172 test)
- **100+ tests** with 80%+ coverage including PostgreSQL-backed E2E integration tests
- **Redis caching** integrated across all external data routes with graceful degradation
- **RAG pipeline** with PDF processing, bge-m3 embeddings, Qdrant vector search
- **8 ORM models**, 8 Alembic migrations, document persistence layer
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
| Subprocess sandbox over Docker | Simpler implementation, sufficient isolation for MVP | — Pending |
| Arq + Redis over Celery + RabbitMQ | Lighter weight, asyncio-friendly, sufficient for current task volume | — Pending (v1.1) |
| APScheduler for scheduling | Mature, simple cron-like scheduling, no additional infrastructure | — Pending (v1.1) |
| PyMuPDF first, OCR as fallback | Fast text extraction handles most PDFs, OCR only for scanned documents | — Pending (v1.1) |
| A-share first, HK later | Reduce scope complexity, validate pipeline with single market first | — Pending (v1.1) |
| API/HTTP over Playwright for data fetching | More stable, testable, lower operational cost than browser automation | — Pending (v1.1) |
| CSI 300 only for MVP | Original plan from PRD, manageable scope for validation | ✓ Good |
| Full RAG with PDF processing | Annual reports are primary analysis source, need semantic search | ✓ Good |
| Multi-agent over single agent | Parallel analysis of risk/valuation/yield is more efficient | — Pending (v1.1) |
| DeepSeek as LLM provider | Cost-effective, strong Chinese language support | ✓ Good |
| Free data sources (AKShare/efinance) | No API key management, no cost for MVP | ✓ Good |
| Audit trail with frozen Pydantic models | Immutable audit data, per-index traceability | ✓ Good |
| Redis graceful degradation | System works without Redis, cache is optimization not dependency | ✓ Good |
| Parent context from Qdrant (not PostgreSQL) | Simpler MVP retriever, single source of truth for vectors | ✓ Good |
| Async PDF processing with BackgroundTasks | Upload returns immediately, processing happens in background | ✓ Good |
| skip_if_no_db pytest marker | Integration tests skip gracefully when no DB available | ✓ Good |
| Document context in ApiResponse meta field | Avoids breaking existing response schemas | ✓ Good |

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
*Last updated: 2026-05-01 after v1.1 milestone start*
