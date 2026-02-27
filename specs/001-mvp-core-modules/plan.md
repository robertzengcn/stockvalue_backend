# Implementation Plan: AI 增强型价值投资决策平台 MVP

**Branch**: `001-mvp-core-modules` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-mvp-core-modules/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

构建一个面向A股/港股严肃投资者的AI增强型价值投资决策辅助系统MVP。系统采用分离式架构，将LLM的语言理解能力与确定性Python计算严格分离，实现三大核心功能：

1. **财务排雷报告（P1）**: 自动计算Beneish M-Score、检测存贷双高异常、商誉占比预警
2. **股息率vs存款利率对比（P2）**: 税后股息率计算与实时存款利率对比
3. **动态DCF估值（P3）**: 基于实时无风险利率的DCF估值与安全边际计算

技术方案采用Hybrid RAG（Qdrant + PostgreSQL/pgvector）处理财报文档，LangGraph编排多Agent工作流，所有财务计算在隔离Docker容器中执行以确保确定性和可追溯性。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: 
- FastAPI (async web framework)
- Pydantic v2 (data validation)
- SQLAlchemy + asyncpg (database ORM)
- LangChain/LangGraph (agent orchestration)
- Tushare/AKShare (financial data APIs)
- Qdrant (vector database)
- Redis (caching)

**Storage**: 
- PostgreSQL 15+ with pgvector extension (structured data + metadata)
- Qdrant (vector embeddings for RAG)
- Redis (result caching)

**Testing**: 
- pytest (test framework)
- pytest-cov (coverage >80%)
- pytest-asyncio (async tests)
- Hypothesis (property-based testing for financial calculations)
- pytest-mock (mocking external APIs)

**Target Platform**: Linux server (Ubuntu 22.04 LTS) with Docker Compose for local development

**Project Type**: Backend-only REST API service (async Python)

**Performance Goals**: 
- 单只股票排雷报告生成 < 30秒
- API响应时间 p95 < 2秒（缓存命中）
- 支持10只股票并发分析（串行处理避免限流）

**Constraints**: 
- 计算必须100%确定性，LLM不执行任何算术运算
- 所有财务计算在隔离Docker容器中执行
- 测试覆盖率必须 >80%
- 类型检查必须通过（mypy --strict）

**Scale/Scope**: 
- MVP阶段仅支持CSI 300成分股
- 年报数据以PDF格式为主
- 预计代码量约10-15k LOC（包括测试）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Type Safety ✓
- All functions will use explicit type hints
- Pydantic models for all data structures
- mypy --strict enforced in CI/CD
- No Any types without documented justification

### Principle II: Deterministic Calculations ✓
- LLMs only extract parameters and interpret results
- All financial calculations performed by pure Python functions
- Calculations executed in isolated Docker containers
- Results include audit trail (inputs, formula, steps)

### Principle III: Separation of Concerns ✓
- Clear layers: models (Pydantic), services (pure functions), api (FastAPI)
- Database logic in repository layer, not in business functions
- No business logic in API endpoints

### Principle IV: Test-Driven Development ✓
- TDD workflow enforced (Red-Green-Refactor)
- pytest with >80% coverage requirement
- Property-based testing for financial calculations (Hypothesis)
- All tests deterministic with fixed seeds

### Principle V: Immutability ✓
- Pydantic models with frozen=True
- Pure functions return new objects
- No mutation of function parameters
- List comprehensions over mutation

**Status**: All gates passed. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-mvp-core-modules/
├── spec.md              # Feature specification (COMPLETE)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
│   ├── risk-api.yaml
│   ├── yield-api.yaml
│   └── valuation-api.yaml
└── tasks.md             # Phase 2 output (NOT created by this command)
```

### Source Code (repository root)

```text
stockvaluefinder/
├── stockvaluefinder/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   │
│   ├── models/                 # Pydantic data models
│   │   ├── __init__.py
│   │   ├── stock.py            # Stock, FinancialReport models
│   │   ├── risk.py             # RiskScore, MScoreData models
│   │   ├── dividend.py         # DividendData, YieldGap models
│   │   └── valuation.py        # ValuationResult, DCFParams models
│   │
│   ├── repositories/           # Database access layer
│   │   ├── __init__.py
│   │   ├── base.py             # Base repository with async session
│   │   ├── stock_repo.py       # Stock data CRUD
│   │   └── rate_repo.py        # Interest rate data
│   │
│   ├── services/               # Business logic (pure functions)
│   │   ├── __init__.py
│   │   ├── risk_service.py     # M-Score, 存贷双高 calculations
│   │   ├── yield_service.py    # Dividend yield, yield gap
│   │   ├── valuation_service.py # DCF calculations
│   │   └── calculation_sandbox.py  # Safe execution environment
│   │
│   ├── agents/                 # LangGraph agent workflows
│   │   ├── __init__.py
│   │   ├── coordinator.py      # Main coordinator agent
│   │   ├── risk_agent.py       # Risk analysis agent
│   │   ├── yield_agent.py      # Yield comparison agent
│   │   └── valuation_agent.py  # DCF valuation agent
│   │
│   ├── rag/                    # RAG processing
│   │   ├── __init__.py
│   │   ├── pdf_processor.py    # PDF to Markdown conversion
│   │   ├── embeddings.py       # bge-m3 embeddings
│   │   ├── vector_store.py     # Qdrant operations
│   │   └── retriever.py        # Hybrid retrieval logic
│   │
│   ├── api/                    # FastAPI endpoints
│   │   ├── __init__.py
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   ├── risk_routes.py      # /api/v1/analyze/risk
│   │   ├── yield_routes.py     # /api/v1/analyze/yield
│   │   └── valuation_routes.py # /api/v1/analyze/dcf
│   │
│   ├── external/               # External API clients
│   │   ├── __init__.py
│   │   ├── tushare_client.py   # Tushare API wrapper
│   │   ├── akshare_client.py   # AKShare API wrapper
│   │   └── rate_client.py      # Interest rate sources
│   │
│   ├── db/                     # Database setup
│   │   ├── __init__.py
│   │   ├── session.py          # Async session factory
│   │   ├── base.py             # SQLAlchemy base
│   │   └── init_db.py          # Database initialization
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── cache.py            # Redis caching utilities
│       ├── logging.py          # Structured logging
│       └── validators.py       # Custom validators
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared pytest fixtures
│   ├── contract/               # API contract tests
│   │   ├── test_risk_api.py
│   │   ├── test_yield_api.py
│   │   └── test_valuation_api.py
│   ├── integration/            # Integration tests
│   │   ├── test_rag_pipeline.py
│   │   ├── test_agent_workflow.py
│   │   └── test_database.py
│   └── unit/                   # Unit tests
│       ├── test_services/
│       │   ├── test_risk_service.py
│       │   ├── test_yield_service.py
│       │   └── test_valuation_service.py
│       ├── test_repositories/
│       └── test_models/
│
├── pyproject.toml              # uv project configuration
├── uv.lock                    # Dependency lock file
├── .env.example               # Environment variables template
├── .pre-commit-config.yaml    # Pre-commit hooks
├── docker-compose.yml         # Local development stack
├── Dockerfile                 # Application container
├── alembic.ini                # Database migration config
└── alembic/                   # Database migrations
    └── versions/
```

**Structure Decision**: Single backend project with clear layered architecture. Models define data structures with Pydantic for validation. Services contain pure business logic functions. Repositories handle database operations. Agents orchestrate LLM workflows. API layer exposes FastAPI endpoints with request/response validation. Testing mirrors source structure with unit, integration, and contract test suites.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitution principles are satisfied by the proposed architecture.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Phase 0: Research & Technical Decisions

Status: ✅ COMPLETE (decisions documented in this plan)

### Research Topics & Decisions

| Topic | Decision | Rationale | Alternatives Considered |
|-------|----------|-----------|------------------------|
| **LLM Provider** | Claude 3.5 Sonnet (primary), DeepSeek-V3 (backup) | Superior reasoning for financial analysis, strong tool-use support | GPT-4o (good but more expensive), local models (insufficient capability) |
| **Vector DB** | Qdrant (Docker) | Open-source, good Python client, hybrid search support | Pinecone (managed, cost), Milvus (complex setup), pgvector only (limited vector features) |
| **RAG Strategy** | Parent-Document Retrieval | 500-token chunks for search, return 2000-token parent for context | Simple chunking (loses context), full document (too expensive) |
| **Embedding Model** | bge-m3 (FlagAlpha) | Optimized for Chinese financial terminology | text-embedding-3-large (good but expensive), jina-embeddings (less Chinese optimized) |
| **Agent Framework** | LangGraph | State machine workflow, supports loops and validation | LangChain Agents (less control), AutoGen (complex), custom (reinventing wheel) |
| **Calculation Sandbox** | Docker + RestrictedPython | Full isolation, resource limits, security | PyPy sandbox (less isolation), subprocess only (no resource limits) |
| **Caching Strategy** | Redis with 24h TTL | Fast lookups, automatic expiration, supports tags | In-memory (lost on restart), PostgreSQL (slower), Memcached (less features) |
| **PDF Processing** | Unstructured.io (primary), Marker (backup) | Handles tables well, outputs Markdown | pdfplumber (poor tables), PyPDF2 (loses formatting), Tesseract OCR (slow, errors) |
| **Data Source Priority** | Tushare (primary), AKShare (backup) | Tushare has better quality, AKShare is free fallback | akshare only (less reliable), scraping (fragile, expensive) |

### Key Technical Patterns

1. **Hybrid RAG**: Metadata filter in PostgreSQL → Vector similarity search in Qdrant → Parent document retrieval
2. **Agent Orchestration**: LangGraph state machine with validation loops and error recovery
3. **Calculation Isolation**: All math in pure Python → executed in Docker container → result returned with audit trail
4. **Type Safety**: Pydantic frozen models + mypy strict mode → no runtime type errors
5. **Async/Await**: FastAPI + SQLAlchemy async → non-blocking I/O for concurrent requests

---

## Phase 1: Design Artifacts

Status: 🔄 IN PROGRESS

See [data-model.md](data-model.md), [contracts/](contracts/), and [quickstart.md](quickstart.md) for detailed design outputs.

### Data Model Summary

Core entities:
- **Stock**: 股票基本信息（代码、名称、市场、行业）
- **FinancialReport**: 财报数据（营收、利润、现金流、资产负债）
- **RiskScore**: 风险评分（M-Score、存贷双高、商誉占比）
- **DividendData**: 分红数据（每股股利、税率、频率）
- **ValuationResult**: 估值结果（内在价值、WACC、安全边际）
- **RateData**: 利率数据（国债收益率、存款利率、更新时间）

### API Contracts

RESTful endpoints following OpenAPI 3.0 spec:
- `POST /api/v1/analyze/risk` - 财务排雷分析
- `POST /api/v1/analyze/yield` - 股息率对比
- `POST /api/v1/analyze/dcf` - DCF估值

All endpoints use standardized response envelope with Pydantic validation.

### Agent Context Update

Run `update-agent-context.sh` after Phase 1 completion to update Claude Code context with new technology stack.

---

## Phase 2: Implementation Tasks

Status: ⏳ NOT STARTED (will be created by `/speckit.tasks` command)

See [tasks.md](tasks.md) for detailed task breakdown (to be generated).

### High-Level Implementation Phases

1. **Foundation Setup** (Week 1): Project structure, dependencies, CI/CD, database schema
2. **Data Layer** (Week 2): Tushare/AKShare integration, PostgreSQL models, Qdrant setup
3. **RAG Pipeline** (Week 3): PDF processing, embeddings, hybrid retrieval
4. **Core Services** (Week 4): Risk calculation, yield gap, DCF (pure Python, deterministic)
5. **Agent Workflows** (Week 5): LangGraph agents with state machine orchestration
6. **API Layer** (Week 6): FastAPI endpoints with Pydantic validation, error handling
7. **Testing & Polish** (Week 7): >80% coverage, property-based tests, documentation

### Quality Gates

Each phase must pass:
1. `uv run mypy --strict .` - Zero type errors
2. `uv run ruff check .` - Zero lint warnings
3. `uv run pytest --cov` - >80% coverage
4. `uv run bandit -r .` - No high-severity security issues

---

## Post-Design Constitution Re-Check

*After Phase 1 design completion*

✅ **Type Safety**: All models use Pydantic with frozen=True, services use explicit type hints
✅ **Deterministic Calculations**: Services are pure functions, calculations isolated in sandbox
✅ **Separation of Concerns**: Clear layers (models → repositories → services → api)
✅ **Test-Driven Development**: pytest structure mirrors source, property-based tests for calculations
✅ **Immutability**: Pydantic frozen models, pure functions return new objects

**Result**: All principles satisfied. Design approved for implementation.
