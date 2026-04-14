# Technology Stack -- New Milestone Additions

**Project:** StockValueFinder -- RAG Pipeline, Multi-Agent Orchestration, Redis Caching
**Researched:** 2026-04-14
**Scope:** Additions to existing FastAPI + SQLAlchemy + PostgreSQL backend

## Context

This document covers ONLY new technologies needed for the next milestone. The existing stack (FastAPI, SQLAlchemy 2.0, Pydantic 2, PostgreSQL + asyncpg, AKShare, efinance, Pydantic, pytest, ruff, mypy) is established and not re-evaluated here. See `.planning/codebase/STACK.md` for the current stack.

The new milestone adds four capabilities:
1. **RAG Pipeline** -- PDF upload, chunking, embeddings, vector search, retrieval
2. **Multi-Agent Orchestration** -- Coordinator + risk/valuation/yield agents via LangGraph
3. **Redis Caching** -- Integrate existing CacheManager into routes/services
4. **Subprocess Calculation Sandbox** -- Resource-limited Python execution

---

## Recommended Stack

### RAG Pipeline

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Docling | >=2.84.0 | PDF-to-Markdown/JSON conversion with table extraction | Best-in-class 97.9% table cell accuracy for financial tables. Native layout analysis preserves reading order. Built-in OCR for scanned Chinese annual reports. Exports structured tables critical for balance sheets and income statements. IBM-backed, actively maintained (v2.84.0 released 2026-04-01). | HIGH |
| langchain-docling | latest | LangChain integration for Docling | Official integration from docling-project. Provides DoclingLoader that feeds directly into LangChain document pipeline, avoiding custom adapter code. | MEDIUM |
| FastEmbed | >=0.8.0 | Local embedding generation with bge-m3 | Built by Qdrant team, same ecosystem as qdrant-client. Runs on ONNX Runtime (no GPU/PyTorch needed). Natively supports BAAI/bge-m3 (1024-dim, multilingual, dense+sparse+ColBERT). Lightweight enough for serverless. v0.8.0 released 2026-03-23. | HIGH |
| qdrant-client | >=1.17.1 | Vector database client (already in deps) | Already in pyproject.toml. Full async support. FastEmbed integration via qdrant-client[fastembed]. Tiered multitenancy (v1.16+) and disk-efficient search for scaling. | HIGH |
| langchain-qdrant | >=1.1.0 | LangChain vector store integration for Qdrant | Official LangChain partner package. Provides QdrantVectorStore that works with LangChain retriever interface. v1.1.0 released 2025-10-22. Eliminates custom vector store adapter code. | HIGH |

### Multi-Agent Orchestration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| LangGraph | >=1.1.6 | Stateful agent orchestration via StateGraph | Already in pyproject.toml (currently >=1.0.9, needs upgrade). v1.1.6 released 2026-04-03. Production-stable (5 - Production/Stable on PyPI). Provides durable execution, state management, conditional edges. LangChain team recommended framework for all agent implementations. Ideal for coordinator pattern: supervisor node dispatches to risk/valuation/yield sub-agents. | HIGH |
| langchain-deepseek | latest | Native DeepSeek LLM integration | Replaces the current langchain-openai + base_url hack for DeepSeek. Official LangChain partner package with dedicated ChatDeepSeek class. Better error handling, model-specific defaults, and direct support. The existing langchain-openai approach still works but is the legacy path. | MEDIUM |
| langgraph-supervisor | latest | Supervisor multi-agent pattern | Official helper library for creating hierarchical multi-agent systems. Implements the supervisor pattern where a coordinator agent dispatches work to specialized sub-agents. Avoids writing boilerplate routing/conditional-edge code. | MEDIUM |

### Redis Caching

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| redis (redis-py) | >=7.2.1 | Async Redis client (already in deps) | Already implemented in utils/cache.py with CacheManager, decorators @cache_result and @invalidate_cache. Just needs integration into services/routes. No new packages needed. | HIGH |

### Calculation Sandbox

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python stdlib subprocess | stdlib | Subprocess-based code execution | subprocess.Popen with timeout via .communicate(timeout=X). Use OS-level resource module for RLIMIT_CPU and RLIMIT_AS memory caps. No external dependency needed. Kill subprocess and children on timeout using process groups. Consistent with project decision to avoid Docker for MVP. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| PyMuPDF | >=1.27.0 | Fast text extraction from PDFs | Use alongside Docling for raw text extraction where Docling AI pipeline is overkill. PyMuPDF is 10x faster for plain text. Use Docling for tables, PyMuPDF for MD&A text sections. Chinese CJK text handled natively. | MEDIUM |
| langchain-text-splitters | latest | Document chunking for RAG | LangChain recursive text splitter and parent-document retriever. Needed for the 500-token chunk / 2000-token parent pattern specified in CLAUDE.md. | HIGH |

---

## Alternatives Considered

### PDF Processing

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| PDF conversion | Docling | PyMuPDF alone | PyMuPDF excels at text extraction but lacks table structure recognition (97.9% accuracy gap). Financial reports are table-heavy. |
| PDF conversion | Docling | Marker | Marker is good for academic papers but less proven on financial report tables. Docling TableFormer module specifically designed for structured data extraction. |
| PDF conversion | Docling | Unstructured.io | Heavier (more dependencies), licensing complexity for production, and Docling benchmarks higher on table extraction. |
| PDF conversion | Docling | LlamaParse | Cloud API service (not local), introduces latency and cost, sends financial data to third parties -- compliance risk for Chinese financial data. |
| PDF conversion | Docling | pdfplumber | Good for simple tables but struggles with complex merged cells common in Chinese financial reports. Docling AI-based approach handles these better. |

### Embeddings

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Embedding model | FastEmbed (bge-m3) | FlagEmbedding directly | FlagEmbedding requires PyTorch (2+ GB), GPU preference, and more complex setup. FastEmbed uses ONNX Runtime (lightweight, CPU-first, same model quality). |
| Embedding model | FastEmbed (bge-m3) | OpenAI embeddings | API-based means network latency per embedding call, cost per token, and sending Chinese financial data to external service. Local is faster and cheaper for batch CSI 300 processing. |
| Embedding model | FastEmbed (bge-m3) | Cohere embed v3 | API-based, same latency/cost/privacy concerns. bge-m3 specifically trained for multilingual retrieval including Chinese. |
| Embedding model | FastEmbed (bge-m3) | sentence-transformers | Heavier dependency (PyTorch), bge-m3 has better multilingual benchmark scores specifically for Chinese. |

### Agent Orchestration

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Agent framework | LangGraph | CrewAI | CrewAI is higher-level and more opinionated. LangGraph provides low-level control needed for deterministic agent architecture (LLM for understanding, Python for calculations). CrewAI abstractions would fight the "calculations in code, not LLM" principle. |
| Agent framework | LangGraph | AutoGen (Microsoft) | AutoGen focuses on conversational multi-agent patterns. StockValueFinder needs graph-based state machine with conditional edges for validation loops, not free-form agent chat. |
| Agent framework | LangGraph | Custom state machine | LangGraph provides durable execution, state checkpointing, and LangSmith observability for free. Writing custom graph orchestration would be reinventing LangGraph poorly. |

### LLM Provider

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| DeepSeek integration | langchain-deepseek | langchain-openai (current) | Current approach works but is legacy path. langchain-deepseek has model-specific features, better error messages, and official support. Worth migrating when convenient but not blocking. |

---

## Version Upgrade Requirements

The following packages in pyproject.toml need version bumps:

| Package | Current Constraint | Recommended Constraint | Reason |
|---------|-------------------|----------------------|--------|
| langgraph | >=1.0.9 | >=1.1.6 | Major stability improvements, production-stable release, new features for durable execution |
| langchain-openai | >=1.1.12 | keep or switch to langchain-deepseek | Current version already recent; consider adding langchain-deepseek alongside |

---

## New Dependencies to Add

```bash
# Core RAG pipeline
uv add docling langchain-docling langchain-qdrant langchain-text-splitters

# Embeddings (FastEmbed -- includes ONNX Runtime)
uv add fastembed

# Agent orchestration (upgrade existing)
uv add "langgraph>=1.1.6"

# Optional: native DeepSeek integration (can coexist with langchain-openai)
uv add langchain-deepseek

# Optional: PyMuPDF for fast text extraction alongside Docling
uv add PyMuPDF
```

Note: qdrant-client is already in dependencies. FastEmbed can also be installed via `qdrant-client[fastembed]` but separate installation gives more control.

---

## What NOT to Use

| Do NOT Use | Reason |
|------------|--------|
| Unstructured.io | Heavy dependency tree, licensing complexity, Docling benchmarks better for tables |
| LlamaParse | Cloud API, sends financial data externally, cost per page |
| FlagEmbedding (direct) | Requires PyTorch (2GB+), FastEmbed provides same model via lightweight ONNX |
| sentence-transformers | PyTorch dependency, bge-m3 via FastEmbed is lighter and better for Chinese |
| CrewAI | Too opinionated, fights deterministic calculation architecture |
| AutoGen | Designed for conversational agents, not graph-based financial analysis workflows |
| Docker-based sandbox | Out of scope per project decision; subprocess sufficient for MVP |
| Marker | Academic paper focus, less proven on financial table structures |
| PaddleOCR | Only needed for scanned PDFs; Docling has built-in OCR. Add later if Docling OCR proves insufficient for specific Chinese annual report formats |

---

## Architecture Integration Notes

### RAG Pipeline Flow

```
PDF Upload -> Docling (PDF->Markdown with tables)
  -> langchain-docling (Document objects)
  -> langchain-text-splitters (500-token chunks, 2000-token parents)
  -> FastEmbed bge-m3 (embed chunks locally)
  -> Qdrant (store vectors + metadata)
  -> langchain-qdrant (retrieval with filters)
  -> LangGraph agents (consume retrieved context)
```

### Agent Orchestration Pattern

```
CoordinatorAgent (supervisor via LangGraph StateGraph)
  -> dispatch to RiskAgent (M-Score, F-Score calculation)
  -> dispatch to ValuationAgent (DCF parameters extraction)
  -> dispatch to YieldAgent (dividend yield calculation)
  -> aggregate results
  -> NarrativeService (DeepSeek LLM for Chinese explanation)
```

### Cache Integration Pattern

```
Route -> Service (check CacheManager.get) -> ExternalDataService (fetch) -> CacheManager.set -> Return
Key scheme: "financial:{ticker}:{fiscal_year}:{source}" TTL=86400
Key scheme: "price:{ticker}" TTL=300
Key scheme: "rate:cn_10y" TTL=3600
```

---

## Sources

- [LangGraph PyPI -- v1.1.6 (2026-04-03)](https://pypi.org/project/langgraph/) -- Verified current
- [Docling GitHub -- v2.84.0 (2026-04-01)](https://github.com/docling-project/docling) -- Verified current
- [Docling PyPI](https://pypi.org/project/docling/) -- Verified exists
- [FastEmbed PyPI -- v0.8.0 (2026-03-23)](https://pypi.org/project/fastembed/) -- Verified current
- [Qdrant Client GitHub -- v1.17.1](https://github.com/qdrant/aqdrant-client/releases) -- Verified current
- [langchain-qdrant PyPI -- v1.1.0 (2025-10-22)](https://pypi.org/project/langchain-qdrant/) -- Verified current
- [langchain-openai PyPI -- v1.1.12 (2026-03-23)](https://pypi.org/project/langchain-openai/) -- Verified current
- [langchain-deepseek Reference](https://reference.langchain.com/python/langchain-deepseek) -- Verified exists
- [PyMuPDF PyPI -- v1.27.2.2 (2026-03-20)](https://pypi.org/project/PyMuPDF/) -- Verified current
- [redis-py GitHub -- v7.4.0](https://github.com/redis/redis-py) -- Verified current
- [PDF Data Extraction Benchmark 2025 (Docling 97.9% table accuracy)](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/) -- MEDIUM confidence benchmark
- [Docling Technical Report (arXiv 2408.09869)](https://arxiv.org/html/2408.09869v4) -- Verified
- [LangGraph Supervisor Pattern](https://github.com/langchain-ai/langgraph-supervisor-py) -- Verified exists
- [freeCodeCamp FinanceGPT with LangGraph](https://www.freecodecamp.org/news/how-to-develop-ai-agents-using-langgraph-a-practical-guide/) -- Reference example
