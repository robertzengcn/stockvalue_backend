# Technology Stack

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
  - **Anthropic Claude** (langchain-anthropic, ChatAnthropic)
  - **DeepSeek** (langchain-openai, OpenAI-compatible API)
  - **OpenAI GPT** (langchain-openai)
  - **Custom OpenAI-compatible** (configurable base URL)
  - **Local Ollama** (langchain-community)
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
