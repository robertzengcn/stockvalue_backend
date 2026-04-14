# External Integrations

## Data Source Integrations

### AKShare Client (`external/akshare_client.py`)
- **Type**: Free, open-source Python library
- **Auth**: No API key required
- **Data provided**: Stock info, daily OHLCV, balance sheet, income statement, cash flow, dividends, shares outstanding
- **API patterns**: Synchronous library wrapped in `asyncio.run_in_executor` for async compatibility
- **Field names**: English field names (e.g., `TOTAL_OPERATE_INCOME`, `NETCASH_OPERATE`)
- **Used as**: Primary data source for most operations

### Tushare Client (`external/tushare_client.py`)
- **Type**: Pro API requiring token
- **Auth**: Token-based (`TUSHARE_TOKEN` env var)
- **Data provided**: Income statements, balance sheets, cash flow, daily market data, dividends, stock basics
- **API patterns**: Async context manager, synchronous library in thread pool
- **Field names**: English lowercase (e.g., `revenue`, `n_income`, `n_cashflow_act`)
- **Used as**: Tertiary fallback, only source for full financial statements

### efinance Client (`external/efinance_client.py`)
- **Type**: Free, official East Money library
- **Auth**: No API key required
- **Data provided**: Real-time quotes, profit sheets, balance sheets, cash flow sheets
- **API patterns**: Synchronous library wrapped for async
- **Field names**: Chinese field names (e.g., `营业总收入`, `净利润`)
- **Used as**: Primary for spot prices (separate API from kline, more reliable), secondary for financials

### Rate Client (`external/rate_client.py`)
- **Type**: Hybrid (AKShare + static fallbacks)
- **Auth**: No API key (AKShare)
- **Data provided**: China 10Y treasury yield (live), 1Y LPR (live), deposit rates (static PBOC benchmarks)
- **API patterns**: AKShare `bond_china_yield` and `macro_china_lpr` in thread pool
- **Fallback rates**: China 10Y=1.82%, 3Y deposit=2.15%, HK 10Y=4.15%, 3Y deposit=4.0%
- **HK rates**: Static only (HKMA API integration pending)

### ExternalDataService (`external/data_service.py`)
- **Unified facade** over all data sources with automatic fallback
- **Priority chain**: AKShare -> efinance -> Tushare -> Mock (dev mode)
- **Dev mode**: `DEVELOPMENT_MODE=true` enables deterministic mock data (hash-based)
- **Lazy initialization**: Call `initialize()` before use, `shutdown()` on cleanup

## LLM Integrations

### LLM Factory (`llm_factory.py`, `llm_config.py`)
- **Factory pattern**: `create_llm(provider=...)` returns LangChain-compatible LLM
- **5 providers**: Anthropic, DeepSeek, OpenAI, Custom (OpenAI-compatible), Local (Ollama)
- **Configuration**: Environment-driven with provider-specific defaults
- **API key resolution**: Provider-specific key -> generic `LLM_API_KEY` fallback
- **Singleton**: `lru_cache` on `LLMSettings.get_config()`

### Narrative Service (`services/narrative_service.py`)
- **Purpose**: Generate Chinese narrative explanations of analysis results via LLM
- **Provider**: Hardcoded to DeepSeek (`create_llm(provider="deepseek")`)
- **Lazy init**: LLM client created on first use, fails gracefully to None
- **Methods**:
  - `generate_narrative()` - generic analysis narrative (risk, yield, valuation)
  - `generate_dcf_explanation()` - step-by-step DCF explanation
- **Response parsing**: Handles JSON, markdown code blocks, mixed text with embedded JSON
- **Graceful degradation**: Returns None on any LLM failure, never crashes the route

## Database Integrations

### SQLAlchemy Setup (`db/base.py`)
- **Engine**: `create_async_engine` with asyncpg driver
- **Session factory**: `async_sessionmaker` with `expire_on_commit=False`
- **Dependency injection**: `get_db()` async generator for FastAPI `Depends`
- **Transaction handling**: Auto-commit on success, auto-rollback on exception
- **Default URL**: `postgresql+asyncpg://svf_admin:...@localhost:5433/stockvaluefinder`

### Alembic Migrations
- Configured via `alembic.ini` at package root
- 7 ORM model files in `db/models/`

## Caching

### Redis Cache (`utils/cache.py`)
- **CacheManager**: Async Redis client with connection pooling
- **Operations**: get, set (with TTL), delete, delete_by_pattern, exists, clear
- **Decorators**: `@cache_result` (TTL-based caching), `@invalidate_cache` (pattern-based invalidation)
- **Status**: Implemented but not integrated into routes or services yet
- **Connection**: Lazy via `connect()`/`disconnect()` methods
