# System Architecture

## High-Level Architecture

```
Request Flow:
Client -> FastAPI Route -> ExternalDataService -> [AKShare|efinance|Tushare]
                           -> [RiskService|ValuationService|YieldService] (pure calculation)
                           -> NarrativeService -> LLM (DeepSeek)
                           -> Repository -> PostgreSQL
                           -> ApiResponse (envelope)
```

## Layered Architecture

```
┌─────────────────────────────────────────────────┐
│  API Layer (api/)                                │
│  risk_routes, valuation_routes, yield_routes     │
├─────────────────────────────────────────────────┤
│  Service Layer (services/)                       │
│  risk_service, valuation_service, yield_service  │
│  narrative_service, narrative_prompts            │
│  calculation_sandbox (TODO)                      │
├─────────────────────────────────────────────────┤
│  Repository Layer (repositories/)                │
│  risk_repo, valuation_repo, yield_repo           │
│  stock_repo, financial_repo, rate_repo           │
│  dividend_repo, base                             │
├─────────────────────────────────────────────────┤
│  External Data Layer (external/)                 │
│  data_service (facade), akshare_client           │
│  efinance_client, tushare_client, rate_client    │
├─────────────────────────────────────────────────┤
│  Domain Models (models/)                         │
│  Pydantic models + DB ORM models (db/models/)    │
├─────────────────────────────────────────────────┤
│  Infrastructure (db/, utils/)                    │
│  SQLAlchemy engine, Redis cache, error classes   │
└─────────────────────────────────────────────────┘
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

1. **Repository Pattern**: BaseRepository[T] generic with specialized subclasses
2. **Service Layer**: Pure functions for calculations, class wrappers for interface consistency
3. **Factory Pattern**: LLM Factory for multi-provider support
4. **Facade Pattern**: ExternalDataService unifies multiple data sources
5. **Graceful Degradation**: Narrative service returns None on LLM failure
6. **Dependency Injection**: FastAPI Depends for DB sessions, data service

## Database Schema (from db/models/)

### Core Tables
- **stocks**: ticker (PK), name, market, sector, listed_date
- **financial_reports**: report_id (PK), ticker (FK), period, fiscal_year, income/balance/cashflow fields
- **valuation_results**: valuation_id (PK), ticker (FK), current_price, intrinsic_value, wacc, margin_of_safety, dcf_params (JSON), audit_trail (JSON)
- **risk_scores**: score_id (PK), ticker (FK), report_id (FK), risk_level, m_score, f_score, mscore_data (JSON), fscore_data (JSON), red_flags (JSON)
- **yield_gap_analyses**: analysis_id (PK), ticker (FK), cost_basis, yields, rates, recommendation
- **dividends**: dividend records
- **rates**: interest rate history
