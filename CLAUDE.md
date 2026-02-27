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

All business and technical documentation is in the `doc/` folder. When making implementation decisions, reference:

- `AI-enhanced value investing decision platform.md` - Product requirements
- `Core technology architecture and implementation documentation.md` - Technical implementation details
- `System_Architecture.md` - System architecture diagrams
- `AI-enhanced_valuation_model.md` - Valuation parameter configurations

## Active Technologies
- Python 3.11+ (001-mvp-core-modules)

## Recent Changes
- 001-mvp-core-modules: Added Python 3.11+
