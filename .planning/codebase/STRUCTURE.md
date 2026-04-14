# Project Structure

## Directory Tree

```
stockvalue_backend/
├── CLAUDE.md                    # Project instructions for Claude Code
├── IMPLEMENTATION_STATUS.md     # Implementation tracking
├── doc/                         # Business and technical documentation
│   ├── system_idea.md
│   ├── System_Architecture.md
│   ├── AI-enhanced_valuation_model.md
│   ├── AI-enhanced value investing decision platform.md
│   ├── Core technology architecture and implementation documentation.md
│   ├── ui_advise.md
│   ├── LOCAL_DEVELOPMENT.md
│   ├── Comparison_of_stock_dividends_and_deposit_yield.md
│   ├── M-Score 与 F-Score：投资分析.md
│   ├── Additional_Financial_Analysis_Advice.md
│   └── Additional_Financial_Analysis_Technology_Advice.md
├── .planning/                   # GSD planning directory
│   └── codebase/                # Codebase analysis output
│
└── stockvaluefinder/            # Main Python package (sub-project)
    ├── pyproject.toml           # Dependencies and tool config
    ├── pytest.ini               # Test configuration
    ├── alembic.ini              # Database migration config
    ├── Dockerfile               # Development Docker image
    ├── Dockerfile.prod          # Production Docker image
    ├── .pre-commit-config.yaml  # Pre-commit hooks
    ├── uv.lock                  # Dependency lock file
    │
    └── stockvaluefinder/        # Application code
        ├── __init__.py
        ├── main.py              # FastAPI app entry point (121 lines)
        ├── config.py            # App configuration (136 lines, frozen dataclasses)
        ├── llm_factory.py       # LLM client factory (230 lines)
        ├── llm_config.py        # LLM configuration (197 lines)
        │
        ├── api/                 # API route layer
        │   ├── __init__.py
        │   ├── risk_routes.py   # POST /api/v1/analyze/risk (149 lines)
        │   ├── valuation_routes.py # POST /api/v1/analyze/dcf (296 lines)
        │   ├── yield_routes.py  # POST /api/v1/analyze/yield (183 lines)
        │   ├── dependencies.py  # FastAPI DI providers
        │   └── stock_helpers.py # Shared route helpers
        │
        ├── services/            # Business logic (pure functions)
        │   ├── __init__.py
        │   ├── risk_service.py  # M-Score, F-Score, risk detection (533 lines)
        │   ├── valuation_service.py # DCF valuation (340 lines)
        │   ├── yield_service.py # Yield gap analysis (197 lines)
        │   ├── narrative_service.py # LLM narrative generation (232 lines)
        │   ├── narrative_prompts.py # Prompt templates
        │   └── calculation_sandbox.py # TODO: Docker sandbox (27 lines)
        │
        ├── repositories/        # Data access layer
        │   ├── __init__.py
        │   ├── base.py          # Generic BaseRepository (119 lines)
        │   ├── risk_repo.py
        │   ├── valuation_repo.py
        │   ├── yield_repo.py
        │   ├── stock_repo.py
        │   ├── financial_repo.py
        │   ├── rate_repo.py
        │   └── dividend_repo.py
        │
        ├── models/              # Pydantic domain models
        │   ├── __init__.py
        │   ├── api.py           # ApiResponse[T], ApiError, PaginationMeta
        │   ├── enums.py         # RiskLevel, ValuationLevel, Market, YieldRecommendation
        │   ├── financial.py     # Financial report models
        │   ├── stock.py         # Stock models
        │   ├── valuation.py     # DCFParams, ValuationResult, requests/responses
        │   ├── risk.py          # RiskScore, MScoreData, FScoreData
        │   ├── yield_gap.py     # YieldGap, YieldGapCreate
        │   ├── dividend.py      # Dividend models
        │   ├── rate.py          # Rate models
        │   └── narrative.py     # AnalysisNarrative, DCFExplanation, WithNarrative mixins
        │
        ├── db/                  # Database layer
        │   ├── __init__.py
        │   ├── base.py          # SQLAlchemy engine, session factory, get_db (48 lines)
        │   └── models/          # SQLAlchemy ORM models
        │       ├── __init__.py
        │       ├── stock.py
        │       ├── financial.py
        │       ├── valuation.py
        │       ├── risk.py
        │       ├── yield_gap.py
        │       ├── dividend.py
        │       └── rate.py
        │
        ├── external/            # External data source clients
        │   ├── __init__.py
        │   ├── data_service.py  # Unified facade with fallback (1187 lines - LARGEST FILE)
        │   ├── akshare_client.py # AKShare data client
        │   ├── efinance_client.py # efinance data client
        │   ├── tushare_client.py # Tushare data client
        │   └── rate_client.py   # Interest rate client (301 lines)
        │
        ├── agents/              # LLM agent definitions (scaffolding)
        │   ├── __init__.py
        │   ├── coordinator_agent.py
        │   ├── risk_agent.py
        │   ├── valuation_agent.py
        │   └── yield_agent.py
        │
        ├── rag/                 # RAG pipeline (scaffolding)
        │   ├── __init__.py
        │   ├── vector_store.py
        │   ├── retriever.py
        │   ├── embeddings.py
        │   └── pdf_processor.py
        │
        └── utils/               # Shared utilities
            ├── __init__.py
            ├── errors.py        # Custom exception hierarchy (71 lines)
            ├── logging.py       # Logging configuration
            ├── validators.py    # Input validation
            └── cache.py         # Redis CacheManager (292 lines)
    │
    └── tests/                  # Test suite
        ├── unit/
        │   ├── __init__.py
        │   ├── test_external/
        │   │   ├── __init__.py
        │   │   ├── test_akshare_client.py
        │   │   ├── test_efinance_client.py
        │   │   └── test_data_service.py
        │   └── test_services/
        │       ├── __init__.py
        │       ├── test_yield_service.py
        │       └── test_valuation_service.py
```

## Key Files

- **main.py**: FastAPI app with CORS, error handler, 3 routers, lifespan with TODOs
- **config.py**: 5 frozen dataclass configs (Valuation, Risk, Yield, ExternalData, Database)
- **Dockerfile / Dockerfile.prod**: Container images at `stockvaluefinder/` level
- **pyproject.toml**: 31 dependencies, mypy/ruff config

## Code Organization Assessment

### Organization Type: Type-based (layered)
- Code is organized by **technical role** (api, services, repositories, models) rather than by business feature
- This is a common pattern for early-stage projects but may create coupling as features grow

### File Size Analysis
- **Largest file**: `data_service.py` at ~1187 lines (exceeds 800-line guideline)
- **Well-sized files**: `risk_service.py` (533), `valuation_routes.py` (296), `cache.py` (292)
- **Stub files**: `calculation_sandbox.py` (27 lines, TODO), agent files, RAG files

### Coupling Analysis
- **API layer** depends on: services, repositories, external, models, db
- **Services** are well-isolated: pure functions with no external dependencies
- **Repositories** depend on: db models, base repository
- **External layer** is self-contained: only depends on utils/errors
- **Risk**: API routes have too many responsibilities (fetch data, analyze, save, generate narrative)
