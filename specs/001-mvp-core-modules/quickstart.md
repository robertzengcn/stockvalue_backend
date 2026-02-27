# Quickstart Guide: StockValueFinder MVP

**Feature**: 001-mvp-core-modules  
**Last Updated**: 2026-02-26

This guide will help you set up the development environment and run the StockValueFinder MVP application.

## Prerequisites

- Python 3.11 or later
- Docker and Docker Compose
- uv (Python package manager) - https://github.com/astral-sh/uv
- Git
- Tushare Pro API token (or use AKShare for free tier)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd stockvaluefinder
```

### 2. Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

Required environment variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/stockvaluefinder

# Vector Database
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Redis
REDIS_URL=redis://localhost:6379/0

# Tushare API (get token from https://tushare.pro)
TUSHARE_TOKEN=your_tushare_token_here

# LLM API
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here  # Optional backup

# Application
LOG_LEVEL=INFO
CACHE_TTL=86400
```

### 4. Start Infrastructure Services

```bash
# Start PostgreSQL, Qdrant, and Redis
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 5. Initialize Database

```bash
# Run database migrations
uv run alembic upgrade head

# Load initial data (optional)
uv run python -m stockvaluefinder.scripts.load_initial_data
```

### 6. Start Development Server

```bash
uv run python -m stockvaluefinder.main
```

The API will be available at http://localhost:8000

## Development Workflow

### Code Quality Checks

Before committing code, run these checks:

```bash
# Type checking
uv run mypy --strict .

# Linting
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Run tests
uv run pytest --cov

# Security check
uv run bandit -r .
```

All checks must pass before pushing to remote.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_services/test_risk_service.py

# Run with coverage
uv run pytest --cov=stockvaluefinder --cov-report=html

# Run property-based tests
uv run pytest tests/unit/test_services/test_risk_service.py -k hypothesis

# Run integration tests
uv run pytest tests/integration/

# Run contract tests
uv run pytest tests/contract/
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "Add goodwill ratio field"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

## API Usage Examples

### 1. Risk Analysis (财务排雷)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/risk \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "600519.SH"
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "risk_level": "LOW",
    "m_score": {
      "total": -2.34,
      "components": {
        "dsri": 0.92,
        "gmi": 1.05,
        ...
      }
    },
    "存贷双高": {
      "detected": false
    },
    "red_flags": []
  },
  "error": null,
  "meta": {
    "processing_time_ms": 1523,
    "cache_hit": false
  }
}
```

### 2. Yield Gap Comparison (股息率对比)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/yield \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "0700.HK",
    "cost_basis": 300.00
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "ticker": "0700.HK",
    "current_price": 310.50,
    "dividend": {
      "dividend_per_share": 12.50,
      "gross_dividend_yield": 0.0402,
      "tax_rate": 0.20,
      "net_dividend_yield": 0.0322
    },
    "risk_free_rates": {
      "ten_year_treasury": 0.0275,
      "three_year_deposit": 0.0225,
      "risk_free_rate": 0.0275
    },
    "yield_gap": 0.0047,
    "recommendation": "NEUTRAL"
  }
}
```

### 3. DCF Valuation (动态估值)

```bash
curl -X POST http://localhost:8000/api/v1/analyze/dcf \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "000002.SZ",
    "growth_rate_stage1": 0.05
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "ticker": "000002.SZ",
    "current_price": 8.50,
    "parameters": {
      "wacc": 0.084,
      "growth_rate_stage1": 0.05,
      ...
    },
    "valuation": {
      "intrinsic_value": 12.25,
      "margin_of_safety": 0.4412,
      "valuation_level": "UNDERVALUED"
    },
    "audit_trail": {
      "calculation_steps": [
        "WACC = Rf + β × ERP = 0.018 + 1.2 × 0.055 = 0.084",
        ...
      ]
    }
  }
}
```

## Project Structure

```
stockvaluefinder/
├── stockvaluefinder/
│   ├── models/              # Pydantic data models
│   ├── repositories/        # Database access layer
│   ├── services/            # Business logic (pure functions)
│   ├── agents/              # LangGraph agent workflows
│   ├── rag/                 # RAG processing
│   ├── api/                 # FastAPI endpoints
│   ├── external/            # External API clients
│   └── db/                  # Database setup
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # API contract tests
└── pyproject.toml           # Project dependencies
```

## Common Tasks

### Add a New Dependency

```bash
# Add to project
uv add fastapi

# Add as dev dependency
uv add --dev pytest-mock
```

### View Logs

```bash
# Application logs
tail -f logs/app.log

# Docker logs
docker-compose logs -f postgres
docker-compose logs -f qdrant
docker-compose logs -f redis
```

### Reset Database

```bash
# Stop containers
docker-compose down

# Remove volumes
docker-compose down -v

# Re-initialize
docker-compose up -d
uv run alembic upgrade head
```

### Run Calculation Sandbox Manually

```bash
uv run python -m stockvaluefinder.utils.sandbox_executor \
  --code "print(2 + 2)" \
  --timeout 10
```

## Troubleshooting

### Issue: "Module not found" error

**Solution**: Make sure you've run `uv sync` to install dependencies.

### Issue: Database connection failed

**Solution**: Check that PostgreSQL is running:
```bash
docker-compose ps
docker-compose logs postgres
```

### Issue: Qdrant connection failed

**Solution**: Verify Qdrant is accessible:
```bash
curl http://localhost:6333/collections
```

### Issue: "Tushare API rate limit exceeded"

**Solution**: The system will automatically fall back to AKShare. You can also:
1. Upgrade your Tushare membership
2. Increase caching duration in `.env`
3. Use API response caching

### Issue: Mypy type errors

**Solution**: 
1. Run `uv run mypy --strict .` to see all errors
2. Add type hints to fix errors
3. Use `# type: ignore` sparingly with justification

## Performance Tips

1. **Enable Caching**: All API responses are cached by default. Adjust `CACHE_TTL` in `.env`.
2. **Batch Requests**: When analyzing multiple stocks, use the batch endpoint (coming in v1.1).
3. **Warm Up Cache**: Run nightly batch jobs to pre-compute valuations for popular stocks.
4. **Monitor Redis Hit Rate**: Use `redis-cli info stats` to check cache effectiveness.

## Getting Help

- Documentation: See `/doc` folder
- Architecture: See [System_Architecture.md](../../doc/System_Architecture.md)
- API Contracts: See [contracts/](contracts/)
- Issue Tracker: Create an issue on GitHub

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes following constitution principles
3. Run all quality checks
4. Submit pull request with description

See [CONSTITUTION.md](../../stockvaluefinder/.specify/memory/constitution.md) for development guidelines.
