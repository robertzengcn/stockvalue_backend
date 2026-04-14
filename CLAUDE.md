# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**StockValueFinder** is an AI-enhanced value investment decision platform for A-share and Hong Kong stock markets. The platform uses LLM agents to analyze financial reports, perform dynamic valuations, and provide risk screening for serious value investors.

### Core Value Proposition

The system solves three key pain points for value investors:
1. **Information Overload** - Automatically parse and extract insights from 200+ page annual reports
2. **Financial Fraud Detection** - Identify manipulation risks using Beneish M-Score and semantic analysis
3. **Dynamic Valuation** - Real-time DCF models with live risk-free rates and yield gap analysis

## Architecture

The system uses a **deterministic agent architecture** where LLMs handle understanding and task decomposition, while traditional tools perform exact calculations:

```
Data Ingestion → RAG Processing → Agent Orchestration → Deterministic Tools → User Dashboard
```

### Key Architectural Principles

1. **Separation of Concerns**: LLMs for natural language understanding, Python/SQL for calculations
2. **Hybrid RAG**: Vector search (Qdrant) + structured metadata (PostgreSQL with pgvector)
3. **Deterministic Tools**: All financial calculations executed in isolated Python REPL, never by LLMs directly
4. **Agentic Workflow**: LangGraph-based state machine for multi-step analysis with validation loops

### Technology Stack

- **LLM**: Claude 3.5 Sonnet, DeepSeek-V3, or GPT-4o for reasoning
- **Vector DB**: Qdrant (Docker) with bge-m3 embeddings
- **Relational DB**: PostgreSQL + pgvector
- **Agent Framework**: LangChain / LangGraph
- **Data Sources**: Tushare, AKShare (A/H shares financial data)
- **Document Processing**: Unstructured.io or Marker for PDF→Markdown conversion

## Development Commands

### Package Management

This project uses `uv` for Python package management:

```bash
# Install dependencies
uv sync

# Run Python with uv environment
uv run python <script>

# Add a dependency
uv add <package>
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_module.py

# Run with coverage
uv run pytest --cov=.

# Run single test
uv run pytest tests/test_module.py::test_function
```

### Code Quality

```bash
# Type checking
uv run mypy .

# Linting
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Running the Application

```bash
# Start the development server (when implemented)
uv run python -m stockvaluefinder.main

# Run a specific module
uv run python -m stockvaluefinder.modules.valuation
```

## Project Structure

```
stockvaluefinder/
├── doc/                    # Project documentation and specifications
│   ├── system_idea.md      # Product-market fit analysis
│   ├── System_Architecture.md  # Technical architecture
│   ├── AI-enhanced_valuation_model.md  # Valuation parameters
│   ├── AI-enhanced value investing decision platform.md  # PRD
│   ├── Core technology architecture and implementation documentation.md  # Tech spec
│   └── ui_advise.md        # UI recommendations
│
├── stockvaluefinder/       # Main package directory
│   └── (modules to be implemented)
│
└── CLAUDE.md               # This file
```

## Core Business Logic

### 1. Financial Insight Module

Extracts and validates key financial metrics from reports:
- Revenue, net profit, operating cash flow, gross margin
- Cross-validation: Profit vs. cash flow divergence detection
- Business segment breakdown by product and region

### 2. Valuation Sandbox Module

Dynamic DCF valuation with real-time parameter updates:
- WACC hook to live 10-year treasury yields
- Industry-based growth rate projections using RAG from research reports
- Sensitivity analysis for user-adjusted parameters

**Key Formulas:**
- Discount Rate: WACC = Rf + β × ERP
- Free Cash Flow: FCF = Net Income + Depreciation - CapEx - ΔNWC
- Intrinsic Value: PV(FCF₁...n) + TV

### 3. Yield Gap Engine

Opportunity cost comparison for dividend stocks:
- After-tax dividend yield (accounts for 20% HK Stock Connect tax)
- Yield gap = Net Dividend Yield - max(Rf_bond, Rf_deposit)
- Red warning when yield gap < 0

### 4. Risk Shield Module

Financial fraud detection using:
- **Beneish M-Score**: 8-factor manipulation detection (threshold: -1.78)
- **"存贷双高" Detection**: High cash + high debt anomaly
- **Semantic Conflict Check**: MD&A vs. auditor opinion inconsistency

## Critical Development Guidelines

### Financial Calculations

**NEVER let LLMs perform arithmetic.** All calculations must:
1. Extract parameters via LLM
2. Generate Python code
3. Execute in isolated Docker container
4. Return structured results with audit trail

### Data Quality

- A-share and H-share data cleaning is complex (accounting standards, AH premium)
- Use Tushare/AKShare APIs, not web scraping for reliability
- Implement dual-source backup for critical data
- Cache results in Redis when no material announcements and price movement < 1%

### RAG Implementation

- Use **Parent-Document Retrieval**: 500-token chunks for search, return 2000-token parent context
- Store metadata (year, industry, ticker) in PostgreSQL for pre-filtering
- bge-m3 embeddings for Chinese financial terminology

### Compliance

- Product positioning: "Investment auxiliary tool" NOT "investment advice"
- Required for China operations: Algorithm registration
- All AI conclusions must link to source document page/paragraph

### Testing and Code Quality (MANDATORY)

**ALL new functions MUST include:**

1. **Unit Tests** (Minimum 80% coverage)
   - Write tests BEFORE implementing the function (TDD approach)
   - Test both success and failure paths
   - Test edge cases and boundary conditions
   - Use pytest with async support for async functions
   - Mock external dependencies (API calls, database)

2. **Code Linting and Formatting**
   - Run `uv run ruff check .` before committing
   - Run `uv run ruff format .` to ensure consistent formatting
   - Run `uv run mypy .` for type checking
   - Fix ALL linting errors before marking task complete

3. **Code Review Checklist**
   - [ ] Unit tests written and passing (80%+ coverage)
   - [ ] Linting passes (ruff check)
   - [ ] Type checking passes (mypy)
   - [ ] Code formatted (ruff format)
   - [ ] Documentation strings added
   - [ ] Error handling implemented
   - [ ] Logging added for debugging

**Testing Commands:**
```bash
# Run tests with coverage
uv run pytest --cov=stockvaluefinder --cov-report=term-missing

# Run linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking
uv run mypy stockvaluefinder/
```

**Example Test Structure:**
```python
# tests/test_external_data_service.py
import pytest
from stockvaluefinder.external.data_service import ExternalDataService

@pytest.mark.asyncio
async def test_get_financial_report_akshare():
    """Test fetching financial report from AKShare."""
    service = ExternalDataService(tushare_token="", enable_akshare=True)
    await service.initialize()

    result = await service.get_financial_report("600519.SH", 2023)

    assert result is not None
    assert result["fiscal_year"] == 2023
    assert "revenue" in result
    assert "net_income" in result
```

## API Design Pattern

Endpoints follow REST conventions with consistent response format:

```python
# Standard response envelope
{
    "success": bool,
    "data": T | None,
    "error": str | None,
    "meta": {
        "total": int,
        "page": int,
        "limit": int
    } | None
}
```

**Key Endpoints:**
- `POST /api/v1/analyze/risk` - M-Score and risk flags
- `POST /api/v1/analyze/yield` - Dividend vs. deposit yield gap
- `POST /api/v1/analyze/dcf` - Dynamic DCF with parameter overrides

## MVP Focus (Phase 1)

**Target Market**: CSI 300 constituents only

**Core Features**:
1. Automatic M-Score calculation for fraud screening
2. Dividend yield vs. large deposit rate comparison chart
3. Batch generate static reports (no interactive chat needed initially)

**Two-Week Sprint Goal**: Validate if target users will pay for 300 screening reports

## Documentation

 When making implementation decisions, reference:

- `AI-enhanced value investing decision platform.md` - Product requirements
- `Core technology architecture and implementation documentation.md` - Technical implementation details
- `System_Architecture.md` - System architecture diagrams
- `AI-enhanced_valuation_model.md` - Valuation parameter configurations

## Active Technologies
- Python 3.12+ (001-mvp-core-modules)
- FastAPI 0.133+
- SQLAlchemy 2.0+
- AKShare 1.14+ (free data source)
- efinance 0.5+ (free data source)

## Recent Changes
- 001-mvp-core-modules: Added Python 3.12+ and FastAPI
- 001-data-sources: Added AKShare and efinance as free data sources
- 001-testing-policy: Added mandatory testing and linting requirements for new functions

<!-- GSD:project-start source:PROJECT.md -->
## Project

**StockValueFinder**

An AI-enhanced value investment decision platform for individual investors analyzing A-share and Hong Kong stocks. The system performs automated financial fraud detection (Beneish M-Score, Piotroski F-Score), dynamic DCF valuation with live risk-free rates, and dividend yield gap analysis. LLM-powered narratives explain analysis results in plain Chinese.

**Core Value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

### Constraints

- **Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, PostgreSQL — established, must keep
- **Data Sources**: AKShare + efinance (free, no API key) as primary — Tushare as optional fallback
- **Stock Universe**: CSI 300 constituents only for this milestone
- **LLM**: DeepSeek as primary provider (cost-effective for Chinese language generation)
- **Vector DB**: Qdrant (already in dependencies, Docker-based)
- **Language**: Chinese for user-facing narratives, English for code/internal
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Runtime & Language
- **Python 3.12+** (required version per pyproject.toml)
- **Package Manager**: uv (modern Python package manager)
- **Build System**: hatchling (via pyproject.toml)
## Web Framework
- **FastAPI 0.133+** - async web framework with automatic OpenAPI docs
- **Uvicorn 0.41+** - ASGI server (with reload for dev)
- **Pydantic 2.12+** - data validation and serialization (v2 with Generic support)
- **CORS middleware** configured for local dev (localhost:5173, 5174, 3000, 8080)
- **Custom exception handler** for `StockValueFinderError` returning structured JSON
## Database
- **PostgreSQL** with **asyncpg** driver (async)
- **SQLAlchemy 2.0+** async ORM with declarative base
- **Alembic 1.18+** for database migrations
- **Connection pooling**: pool_size=5, max_overflow=10
- **7 ORM models**: stock, financial, valuation, risk, yield_gap, dividend, rate
- **Database URL**: via `DATABASE_URL` env var, defaulting to `localhost:5433/stockvaluefinder`
## LLM Integration
- **LLM Factory** (`llm_factory.py`) supporting 5 providers:
- **Default provider**: DeepSeek (hardcoded in NarrativeService)
- **Default model**: claude-3-5-sonnet (for Anthropic), deepseek-chat (for DeepSeek)
- **Configuration**: via env vars (LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, etc.)
- **LLMConfig**: frozen dataclass with validation (temperature, max_tokens)
## External Data Sources
- **AKShare 1.14+** (primary, free, no API key) - A-share stock data, financials, dividends
- **efinance 0.5+** (secondary, free) - East Money real-time quotes, financial statements
- **Tushare** (tertiary, requires token) - financial statements, daily data
- **Fallback chain**: AKShare -> efinance -> Tushare -> Mock (dev mode)
- **RateClient**: AKShare bond_china_yield for treasury yields, static fallbacks for deposit rates
## Agent Framework
- **LangChain 1.2+** / **LangGraph 1.0+** - agent orchestration (imported but not actively used yet)
- **4 agent files defined**: coordinator, risk, valuation, yield (mostly scaffolding)
- **Deterministic architecture**: LLMs for narrative only, Python for calculations
## Vector DB / RAG
- **Qdrant Client 1.17+** (imported, Docker-based planned)
- **RAG module**: vector_store.py, retriever.py, embeddings.py, pdf_processor.py (scaffolding)
- **bge-m3 embeddings** planned for Chinese financial terminology
## Testing
- **pytest 9.0+** with **pytest-asyncio**, **pytest-cov 7.0+**, **pytest-mock 3.15+**
- **hypothesis 6.15+** for property-based testing
- **bandit 1.9+** for security linting
- Unit tests for external clients and services
## DevOps
- **Docker** (Dockerfile, Dockerfile.prod)
- **Pre-commit hooks** (.pre-commit-config.yaml)
- **Ruff 0.15+** for linting and formatting
- **mypy 1.19+** for type checking (pydantic plugin enabled)
## Key Dependencies (from pyproject.toml)
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.133.1 | Web framework |
| sqlalchemy | >=2.0.47 | ORM |
| pydantic | >=2.12.5 | Validation |
| alembic | >=1.18.4 | Migrations |
| asyncpg | >=0.31.0 | PostgreSQL driver |
| redis | >=7.2.1 | Caching |
| httpx | >=0.27.0 | HTTP client |
| akshare | >=1.14.0 | A-share data |
| efinance | >=0.5.6 | East Money data |
| langchain | >=1.2.10 | LLM orchestration |
| langgraph | >=1.0.9 | Agent graphs |
| qdrant-client | >=1.17.0 | Vector DB |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Conventions
### File Naming
- Python modules: `snake_case.py` (e.g., `risk_service.py`, `akshare_client.py`)
- Route files: `{domain}_routes.py` (e.g., `risk_routes.py`, `valuation_routes.py`)
- Repository files: `{domain}_repo.py` (e.g., `risk_repo.py`, `stock_repo.py`)
- Model files: `{domain}.py` (e.g., `risk.py`, `valuation.py`)
### Class Naming
- Services: `{Domain}Service` or `{Domain}Analyzer` (e.g., `RiskAnalyzer`, `DCFValuationService`, `YieldAnalyzer`)
- Repositories: `{Domain}Repository` (e.g., `RiskScoreRepository`, `StockRepository`)
- Models (Pydantic): `{Domain}Result`, `{Domain}Params`, `{Domain}Create` (e.g., `ValuationResult`, `DCFParams`, `RiskScoreCreate`)
- ORM Models: Same names as domain models
- Config: `{Domain}Config` (e.g., `ValuationConfig`, `RiskConfig`)
- Errors: `{Description}Error` extending `StockValueFinderError`
### Function Naming
- Pure calculation functions: `calculate_{metric}` (e.g., `calculate_beneish_m_score`, `calculate_wacc`)
- Detection functions: `detect_{pattern}` (e.g., `detect_存贷双高`)
- Determination functions: `determine_{result}` (e.g., `determine_risk_level`)
- Analysis orchestrators: `analyze_{domain}` (e.g., `analyze_financial_risk`, `analyze_dcf_valuation`)
- Private helpers: `_prefix` (e.g., `_calculate_gross_margin_from_akshare`)
## Code Style
### Type Hints
- **Comprehensive**: All function signatures have type hints
- **Return types**: Always specified (e.g., `-> dict[str, Any]`, `-> RiskScore`)
- **Python 3.12+ syntax**: Uses `X | Y` instead of `Optional[X]`, `list[X]` instead of `List[X]`
- **TypeVar**: Used in BaseRepository generic (e.g., `ModelType`, `CreateSchemaType`)
### Docstring Patterns
- **Google-style docstrings** with Args/Returns/Raises/Examples sections
- **Examples** section with `>>>` doctest format for pure calculation functions
- **Reference** section for academic formulas (e.g., Beneish M-Score paper)
### Error Handling
- **Custom exception hierarchy**: `StockValueFinderError` -> `DataValidationError`, `CalculationError`, `ExternalAPIError`, `CacheError`
- **Error details**: Each exception carries structured `details` dict
- **Route-level handling**: Try/except with specific exception types, returns `ApiResponse(success=False, error=...)`
- **Graceful degradation**: Narrative service catches all exceptions and returns None
### Immutability
- **Config dataclasses**: All `frozen=True` (ValuationConfig, RiskConfig, YieldConfig, etc.)
- **LLMConfig**: `frozen=True` with `__post_init__` validation
- **Pydantic models**: `model_config = {"frozen": True}` on ApiResponse, ApiError, PaginationMeta
- **Domain models**: Some frozen (api.py), but domain models like RiskScore, ValuationResult appear mutable
## API Conventions
### Route Naming
- Prefix: `/api/v1/analyze/{domain}` (e.g., `/api/v1/analyze/risk`)
- Method: POST for analysis operations
- Tags: per domain (`risk`, `valuation`, `yield`)
### Response Format
- Generic `ApiResponse[T]` with Pydantic Generic[DataType]
- Error responses: `success=False, data=None, error="message"`
- Success responses: `success=True, data={domain_result}`
### Request Models
- Pydantic `BaseModel` with `Field(...)` for validation
- Pattern validation for tickers: `r"^\d{6}\.(SH|SZ|HK)$"`
- `Config.json_schema_extra` for examples
### Dependency Injection
- `get_db()`: AsyncSession via `Depends(get_db)`
- `get_initialized_data_service()`: ExternalDataService singleton
- Route signature: `data_service: ExternalDataService = Depends(...)`
## Model Conventions
### Domain vs DB Model Separation
- **Pydantic models** (`models/`): Domain logic, validation, serialization
- **SQLAlchemy ORM models** (`db/models/`): Database persistence, column types
- **Create schemas**: Separate `{Domain}Create` models for repository input
- **Mapping**: Routes manually map between Pydantic and ORM models
### Enums
- `StrEnum` (Python 3.12+): RiskLevel, ValuationLevel, Market, YieldRecommendation
- Used for type-safe categorization
## Configuration
### config.py Patterns
- 5 frozen dataclass configs with sensible defaults
- Singleton via `AppConfig.get_instance()` with `lru_cache`
- Global `settings = AppConfig.get_instance()`
- No env var reading in config.py (pure defaults)
### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`: LLM configuration
- `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`: Provider-specific keys
- `TUSHARE_TOKEN`: Tushare API token
- `DEVELOPMENT_MODE`: Enable mock data ("true"/"false")
- Loaded via `python-dotenv` in main.py
## Import Patterns
- **Absolute imports**: `from stockvaluefinder.services.risk_service import RiskAnalyzer`
- **Lazy imports**: Some heavy imports inside functions (e.g., `import akshare as ak` inside methods)
- **Circular ref handling**: `_rebuild_forward_refs()` called in main.py after all modules loaded
- **Type checking**: `TYPE_CHECKING` guard not used; `# type: ignore` comments for untyped libraries
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## High-Level Architecture
```
```
## Layered Architecture
```
```
## Module Breakdown
### api/ - FastAPI Routes
- **risk_routes.py**: `POST /api/v1/analyze/risk` - M-Score, F-Score, risk analysis
- **valuation_routes.py**: `POST /api/v1/analyze/dcf` - DCF valuation, `POST /api/v1/analyze/dcf/explain` - AI explanation
- **yield_routes.py**: `POST /api/v1/analyze/yield` - Yield gap analysis
- **dependencies.py**: FastAPI dependency injection (get_initialized_data_service)
- **stock_helpers.py**: Shared helpers (ensure_stock_exists, ensure_financial_report_exists)
### services/ - Business Logic (Pure Functions)
- **risk_service.py**: Beneish M-Score (8-factor), Piotroski F-Score (9-point), 存贷双高 detection, goodwill ratio, profit-cash divergence
- **valuation_service.py**: WACC calculation, FCF projection, terminal value, margin of safety, 2-stage DCF
- **yield_service.py**: Net dividend yield (tax-aware), yield gap calculation, recommendation engine
- **narrative_service.py**: LLM narrative generation with graceful fallback
- **narrative_prompts.py**: Prompt templates for risk, valuation, yield, DCF explanation
- **calculation_sandbox.py**: TODO - Docker-based isolated Python execution
### repositories/ - Data Access
- **base.py**: Generic `BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType]` with CRUD
- **risk_repo.py**: RiskScoreRepository with `upsert_by_report_id`
- **valuation_repo.py**: ValuationRepository with `get_by_valuation_id`
- **yield_repo.py**: YieldGapRepository
- **stock_repo.py**: StockRepository with `get_by_ticker`
- **financial_repo.py**: FinancialReportRepository
- **rate_repo.py**: RateRepository
- **dividend_repo.py**: DividendRepository
### models/ - Domain Models (Pydantic)
- **api.py**: `ApiResponse[T]` (generic envelope), `ApiError`, `PaginationMeta` (all frozen)
- **enums.py**: RiskLevel, ValuationLevel, Market, YieldRecommendation
- **financial.py**: Financial report models
- **stock.py**: Stock models
- **valuation.py**: DCFParams, ValuationResult, DCFValuationRequest, DCFExplanationRequest/Response
- **risk.py**: RiskScore, MScoreData, FScoreData, RiskScoreCreate
- **yield_gap.py**: YieldGap, YieldGapCreate
- **dividend.py**: Dividend models
- **rate.py**: Rate models
- **narrative.py**: AnalysisNarrative, DCFExplanation, WithNarrative mixins
### db/models/ - SQLAlchemy ORM Models
- Mirrors domain models: stock, financial, valuation, risk, yield_gap, dividend, rate
- Maps Pydantic models to database tables
### external/ - External Data Clients
- **data_service.py**: ExternalDataService - unified facade with fallback chain
- **akshare_client.py**: AKShareClient - primary free data source
- **efinance_client.py**: EFinanceClient - East Money data
- **tushare_client.py**: TushareClient - token-based data source
- **rate_client.py**: RateClient - interest rate fetching
### agents/ - LLM Agent Definitions (Scaffolding)
- **coordinator_agent.py**: Orchestrator agent
- **risk_agent.py**: Risk analysis agent
- **valuation_agent.py**: Valuation agent
- **yield_agent.py**: Yield analysis agent
### rag/ - RAG Pipeline (Scaffolding)
- **vector_store.py**: Qdrant integration
- **retriever.py**: Document retrieval
- **embeddings.py**: bge-m3 embedding generation
- **pdf_processor.py**: PDF to markdown conversion
### utils/ - Shared Utilities
- **errors.py**: StockValueFinderError hierarchy (DataValidationError, CalculationError, ExternalAPIError, CacheError)
- **logging.py**: Structured logging setup
- **validators.py**: Input validation helpers
- **cache.py**: Redis CacheManager with decorator patterns
## Key Design Patterns
## Database Schema (from db/models/)
### Core Tables
- **stocks**: ticker (PK), name, market, sector, listed_date
- **financial_reports**: report_id (PK), ticker (FK), period, fiscal_year, income/balance/cashflow fields
- **valuation_results**: valuation_id (PK), ticker (FK), current_price, intrinsic_value, wacc, margin_of_safety, dcf_params (JSON), audit_trail (JSON)
- **risk_scores**: score_id (PK), ticker (FK), report_id (FK), risk_level, m_score, f_score, mscore_data (JSON), fscore_data (JSON), red_flags (JSON)
- **yield_gap_analyses**: analysis_id (PK), ticker (FK), cost_basis, yields, rates, recommendation
- **dividends**: dividend records
- **rates**: interest rate history
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
