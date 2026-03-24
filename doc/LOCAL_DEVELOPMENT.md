# Local Development Guide

This guide will help you set up and run the StockValueFinder project on your local machine.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12+** - [Download](https://www.python.org/downloads/)
- **uv** - Fast Python package installer (recommended)
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Docker & Docker Compose** - For running PostgreSQL, Qdrant, and Redis
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows)
  - Or Docker Engine on Linux
- **Git** - For version control

## Quick Start

### 1. Navigate to Project Directory

```bash
cd stockvalue_backend/stockvaluefinder
```

### 2. Install Dependencies

Using `uv` (recommended):

```bash
# Sync dependencies from pyproject.toml
uv sync
```

### 3. Start Infrastructure Services

Start PostgreSQL, Qdrant, and Redis using Docker Compose:

```bash
docker compose up
```

Verify services are running:

```bash
docker-compose ps
```

You should see all three services marked as `healthy`.

### 4. Configure Environment Variables

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` and update the following variables:

```bash
# Required: Get your token from https://tushare.pro
TUSHARE_TOKEN=your_actual_token_here

# Required: Get your API keys from the respective platforms
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Optional: Adjust based on your needs
LOG_LEVEL=INFO
CACHE_TTL=86400
```

**Getting API Keys:**

- **Tushare Token**: Register at [https://tushare.pro](https://tushare.pro) and get your free API token
- **Anthropic API Key**: Get from [https://console.anthropic.com](https://console.anthropic.com)
- **DeepSeek API Key**: Get from [https://platform.deepseek.com](https://platform.deepseek.com)

### 5. Initialize Database

Run database migrations:

```bash
uv run alembic upgrade head
```

### 6. Run the Application

Start the development server:

```bash
uv run python -m stockvaluefinder.main
```

Or using uvicorn directly (for FastAPI):

```bash
uv run uvicorn stockvaluefinder.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI): `http://localhost:8000/docs`

## Development Workflow

### Code Quality Tools

```bash
# Type checking
uv run mypy .

# Linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=.

# Run specific test file
uv run pytest tests/test_module.py

# Run single test
uv run pytest tests/test_module.py::test_function

# Run with verbose output
uv run pytest -v
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description of changes"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Project Structure

```
stockvaluefinder/
├── alembic/                # Database migrations
├── stockvaluefinder/       # Main package
│   ├── agents/            # LangGraph agents
│   ├── api/               # FastAPI endpoints
│   ├── db/                # Database management
│   ├── external/          # External API clients
│   ├── models/            # SQLAlchemy models
│   ├── rag/               # RAG processing
│   ├── repositories/      # Data access layer
│   ├── services/          # Business logic
│   └── utils/             # Utilities
├── tests/                 # Test suite
├── .env.example           # Environment template
├── docker-compose.yml     # Infrastructure
└── pyproject.toml         # Dependencies
```

## Common Issues

### Docker Services Won't Start

```bash
# Check what's using the ports
lsof -i :5433  # PostgreSQL
lsof -i :6333  # Qdrant
lsof -i :6380  # Redis
```

### Database Connection Errors

Ensure Docker services are healthy:

```bash
docker-compose ps
docker-compose logs postgres
```

### Import Errors

Always use `uv run`:

```bash
# Wrong
python -m stockvaluefinder.main

# Correct
uv run python -m stockvaluefinder.main
```

## Development Tips

### View Docker Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
```

### Reset Development Environment

```bash
# Stop and remove volumes
docker-compose down -v

# Clean Python cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Reinstall
uv sync
docker-compose up -d
uv run alembic upgrade head
```

### Database Inspection

```bash
# Connect to PostgreSQL
docker exec -it stockvaluefinder-postgres-1 psql -U user -d stockvaluefinder

# List tables
\dt

# Describe table
\d table_name
```

## Resources

- **Architecture**: `doc/System_Architecture.md`
- **Technical Specs**: `doc/Core technology architecture and implementation documentation.md`
- **Product Requirements**: `doc/AI-enhanced value investing decision platform.md`

---

**Happy coding! 🚀**
