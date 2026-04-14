# StockValueFinder

## What This Is

An AI-enhanced value investment decision platform for individual investors analyzing A-share and Hong Kong stocks. The system performs automated financial fraud detection (Beneish M-Score, Piotroski F-Score), dynamic DCF valuation with live risk-free rates, and dividend yield gap analysis. LLM-powered narratives explain analysis results in plain Chinese.

## Core Value

Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## Requirements

### Validated

<!-- Existing working features from brownfield codebase -->

- ✓ Risk analysis API (M-Score, F-Score, 存贷双高 detection, profit-cash divergence) — existing
- ✓ DCF valuation API (2-stage growth model, WACC, terminal value, margin of safety) — existing
- ✓ Yield gap analysis API (tax-aware dividend yield vs risk-free rates) — existing
- ✓ Multi-source data fetching (AKShare → efinance → Tushare fallback chain) — existing
- ✓ LLM narrative generation (DeepSeek with graceful fallback) — existing
- ✓ Analysis persistence (PostgreSQL with 7 ORM models, Alembic migrations) — existing
- ✓ Standardized API envelope (ApiResponse[T] with error handling) — existing
- ✓ Interest rate fetching (live China 10Y treasury via AKShare, static deposit rates) — existing

### Active

<!-- New features to build -->

- [ ] M-Score indices calculated from raw financial data (currently hardcoded defaults)
- [ ] Redis caching for external data (financial reports 24h, prices 5min, rates 1h)
- [ ] Full RAG pipeline (PDF upload → chunking → bge-m3 embeddings → Qdrant vector search → retrieval)
- [ ] Multi-agent analysis pipeline (coordinator + risk + valuation + yield agents via LangGraph)
- [ ] Subprocess-based calculation sandbox (resource-limited Python execution)
- [ ] Comprehensive test suite (80%+ coverage for services, routes, repositories)

### Out of Scope

- Docker-based calculation sandbox — subprocess sandbox sufficient for MVP
- All A-share + HK stock universe — CSI 300 constituents only for this milestone
- Interactive chat interface — batch static reports sufficient for MVP
- User authentication — single-user system for now
- Frontend application — API-only for this milestone
- Real-time WebSocket updates — not needed for batch analysis
- HKMA live rate fetching — static HK rates acceptable
- Batch report generation for all CSI 300 — individual stock analysis first

## Context

### Current Codebase State
- **Brownfield project** with working FastAPI backend, PostgreSQL database, and 3 analysis APIs
- **LLM integration** via DeepSeek for Chinese narrative generation
- **External data** from AKShare (primary), efinance (secondary), Tushare (tertiary)
- **Tech stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic 2, PostgreSQL, Redis, Qdrant, LangChain/LangGraph

### Key Technical Debt
- M-Score 8 indices hardcoded to 1.0/0.0 defaults — not calculated from actual financial data
- Redis CacheManager implemented but never integrated into routes/services
- RAG module (vector_store, retriever, embeddings, pdf_processor) is scaffolding only
- Agent module (coordinator, risk, valuation, yield) is scaffolding only
- Calculation sandbox is a TODO stub
- Database credentials hardcoded in db/base.py (security issue)
- Low test coverage — no integration tests, risk service untested

### Architecture Pattern
- **Deterministic agent architecture**: LLMs handle understanding/narrative, Python performs exact calculations
- **Layered architecture**: API → Service → Repository → External/DB
- **Pure function services**: All calculations are stateless pure functions
- **Graceful degradation**: LLM narratives return None on failure, never crash

## Constraints

- **Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, PostgreSQL — established, must keep
- **Data Sources**: AKShare + efinance (free, no API key) as primary — Tushare as optional fallback
- **Stock Universe**: CSI 300 constituents only for this milestone
- **LLM**: DeepSeek as primary provider (cost-effective for Chinese language generation)
- **Vector DB**: Qdrant (already in dependencies, Docker-based)
- **Language**: Chinese for user-facing narratives, English for code/internal

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Subprocess sandbox over Docker | Simpler implementation, sufficient isolation for MVP | — Pending |
| CSI 300 only for MVP | Original plan from PRD, manageable scope for validation | — Pending |
| Full RAG with PDF processing | Annual reports are primary analysis source, need semantic search | — Pending |
| Multi-agent over single agent | Parallel analysis of risk/valuation/yield is more efficient | — Pending |
| DeepSeek as LLM provider | Cost-effective, strong Chinese language support | ✓ Good |
| Free data sources (AKShare/efinance) | No API key management, no cost for MVP | ✓ Good |

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
*Last updated: 2026-04-14 after initialization*
