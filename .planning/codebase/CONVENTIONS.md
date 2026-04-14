# Coding Conventions

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
```json
{
    "success": bool,
    "data": T | None,
    "error": str | None,
    "meta": dict | None
}
```
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
