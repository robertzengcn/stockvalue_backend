# Research Document: AI 增强型价值投资决策平台 MVP

**Feature**: 001-mvp-core-modules  
**Date**: 2026-02-26  
**Status**: Complete

This document captures all technical research, decisions, and trade-offs made during Phase 0 of the planning process.

## Research Topics & Decisions

### 1. LLM Provider Selection

**Decision**: Claude 3.5 Sonnet (primary), DeepSeek-V3 (backup)

**Rationale**:
- Superior reasoning capabilities for financial document analysis
- Strong function calling/tool use support for deterministic calculations
- Excellent Chinese language understanding for A股财报
- Competitive pricing vs GPT-4o
- Lower hallucination rate on numerical tasks compared to other models

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|-------------|------|-------|---------|
| GPT-4o | Excellent reasoning, good tool use | More expensive, higher latency | Backup option |
| DeepSeek-V3 | Cost-effective, good Chinese support | Less proven on complex financial tasks | Selected as backup |
| Local Qwen-2.5 | Free, low latency | Higher resource requirements, less capable | Not suitable for MVP |

**Implementation Notes**:
- Use Anthropic Python SDK with automatic retries
- Implement fallback to DeepSeek-V3 if Claude rate limit reached
- Cache LLM responses for identical queries (Redis with 1-hour TTL)
- Use structured outputs (JSON mode) for parameter extraction

---

### 2. Vector Database Selection

**Decision**: Qdrant (Docker deployment)

**Rationale**:
- Open-source with permissive license (Apache 2.0)
- Excellent Python client with async support
- Built-in hybrid search (vector + keyword)
- Good performance on medium-scale datasets (< 10M documents)
- Docker deployment for local development simplicity
- Supports filtering by payload (metadata)

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|-------------|------|-------|---------|
| Pinecone | Managed service, excellent performance | Expensive at scale, vendor lock-in | Too costly for MVP |
| Milvus | Powerful, scalable | Complex setup, resource-heavy | Overkill for MVP |
| pgvector only | Simpler stack | Limited vector features, slower search | Insufficient for RAG needs |

**Implementation Notes**:
- Use Qdrant Docker image version 1.10+
- Collection per market (A-shares, HK stocks)
- Store 768-dim vectors (bge-m3 output)
- Payload filtering: year, industry, ticker, report_type
- HNSW index with m=16, ef_construct=100

---

### 3. RAG Strategy

**Decision**: Parent-Document Retrieval with 500-token child chunks

**Rationale**:
- Balances search precision with context completeness
- Small chunks (500 tokens) enable accurate semantic search
- Parent chunks (2000 tokens) provide sufficient context for LLM reasoning
- Reduces token cost vs retrieving entire documents
- Proven pattern for financial document analysis

**Alternatives Considered**:
| Strategy | Pros | Cons | Verdict |
|----------|------|-------|---------|
| Simple chunking (1000 tokens) | Easy to implement | Loses fine-grained context | Insufficient precision |
| Full document retrieval | Complete context | Very expensive, slow retrieval | Token cost prohibitive |
| Sentence window retrieval | Maximum precision | Complex implementation | Over-engineering for MVP |

**Implementation Notes**:
- Use LangChain's ParentDocumentSplitter
- Child chunk size: 500 tokens, overlap: 50 tokens
- Parent chunk size: 2000 tokens, overlap: 200 tokens
- Store only child vectors in Qdrant
- Retrieve top-5 child chunks → return their parent chunks
- Metadata: ticker, year, report_type (annual/quarterly), section

---

### 4. Embedding Model

**Decision**: bge-m3 (FlagAlpha/BAAI)

**Rationale**:
- State-of-the-art for Chinese financial text
- Supports multi-functionality (dense, sparse, colbert)
- 768-dimensional vectors (good balance of size and performance)
- Trained on diverse Chinese corpora including financial documents
- Open-source with permissive license
- Good inference speed (~50 docs/sec on GPU)

**Alternatives Considered**:
| Model | Pros | Cons | Verdict |
|-------|------|-------|---------|
| text-embedding-3-large | Excellent quality | Expensive API, rate limits | Cost prohibitive |
| jina-embeddings-v2 | Fast, multilingual | Less optimized for Chinese | Lower quality on Chinese financial text |
| paraphrase-multilingual | Good for general text | Not domain-specific | Insufficient for financial terminology |

**Implementation Notes**:
- Use FlagEmbedding library with ONNX runtime
- Batch size: 32 documents
- Normalize vectors before storing in Qdrant
- Cache embeddings to avoid re-computation

---

### 5. Agent Framework

**Decision**: LangGraph

**Rationale**:
- State machine workflow with explicit control flow
- Built-in support for loops and validation
- Good persistence and checkpointing
- Integrates seamlessly with LangChain ecosystem
- Visual debugging with LangSmith
- Better error handling compared to LangChain Agents

**Alternatives Considered**:
| Framework | Pros | Cons | Verdict |
|-----------|------|-------|---------|
| LangChain Agents | Simpler for basic tasks | Limited control, no loops | Insufficient for complex workflows |
| AutoGen | Multi-agent conversations | Complex, over-engineering | Too complex for MVP needs |
| Custom implementation | Full control | Reinventing the wheel | Development time prohibitive |

**Implementation Notes**:
- Define strict TypedState for type safety
- Use StateGraph with conditional edges
- Implement validation nodes after each calculation
- Add human-in-the-loop for error handling
- Enable checkpointing for recovery from failures

---

### 6. Calculation Sandbox

**Decision**: Docker + RestrictedPython

**Rationale**:
- Full process isolation prevents malicious code execution
- Resource limits (CPU, memory, timeout) prevent runaway processes
- Network isolation prevents data exfiltration
- RestrictedPython whitelists safe operations only
- Audit trail by capturing stdout/stderr

**Alternatives Considered**:
| Approach | Pros | Cons | Verdict |
|-----------|------|-------|---------|
| PyPy sandbox | Faster execution | Less isolation, complex setup | Insufficient security |
| Subprocess only | Simple | No resource limits | Unsafe for LLM-generated code |
| No sandbox | Fastest | Major security risk | Unacceptable for production |

**Implementation Notes**:
- Use docker-py for container management
- Base image: python:3.11-slim with minimal packages
- Resource limits: 1 CPU, 512MB RAM, 30s timeout
- Network mode: none (disable all network access)
- Volume mount: read-only access to input data
- Whitelist: pandas, numpy, math, datetime modules only
- Capture execution time and memory usage for monitoring

---

### 7. Caching Strategy

**Decision**: Redis with 24-hour TTL

**Rationale**:
- In-memory caching for sub-millisecond lookups
- Automatic expiration prevents stale data
- Supports tagging for bulk invalidation
- Persistent across restarts (with RDB snapshots)
- Good Python client with async support
- Pub/sub for cache invalidation events

**Alternatives Considered**:
| Approach | Pros | Cons | Verdict |
|-----------|------|-------|---------|
| In-memory (dict) | Fastest | Lost on restart, no sharing | Insufficient reliability |
| PostgreSQL caching | Persistent | Slower, adds DB load | Performance unacceptable |
| Memcached | Faster | No persistence, fewer features | Less feature-rich |

**Implementation Notes**:
- Cache key pattern: `{module}:{ticker}:{date_hash}`
- Tag by ticker for targeted invalidation
- Compress values > 1KB with gzip
- Monitor hit/miss ratio with Prometheus metrics
- Invalidate on price change > 1% or major announcements

---

### 8. PDF Processing

**Decision**: Unstructured.io (primary), Marker (backup)

**Rationale**:
- Unstructured handles tables better than most alternatives
- Outputs Markdown with preserved structure
- Supports Chinese characters natively
- Good Python SDK with async support
- Active development and community
- Handles scanned PDFs with OCR (Tesseract backend)

**Alternatives Considered**:
| Library | Pros | Cons | Verdict |
|---------|------|-------|---------|
| pdfplumber | Fast, simple | Poor table extraction | Insufficient for financial tables |
| PyPDF2 | Widely used | Loses formatting, poor Chinese | Quality unacceptable |
| Marker | Excellent table detection | Slower, newer project | Good backup option |

**Implementation Notes**:
- Use Unstructured with partition_pdf API
- Extract tables as HTML → convert to Markdown
- Preserve document hierarchy (sections, subsections)
- Fallback to Marker if Unstructured fails
- Cache processed Markdown to avoid re-processing

---

### 9. Data Source Priority

**Decision**: Tushare Pro (primary), AKShare (backup)

**Rationale**:
- Tushare has better data quality and coverage
- Pro API with reasonable rate limits
- Good documentation and Python SDK
- AKShare is free and open-source (good backup)
- Both support A-shares and HK stocks

**Alternatives Considered**:
| Source | Pros | Cons | Verdict |
|--------|------|-------|---------|
| AKShare only | Free, no API key needed | Less reliable, rate limits | Data quality concerns |
| Web scraping | Full control | Fragile, expensive, legal risks | Maintenance burden too high |
| Wind/Choice | Professional data | Very expensive, enterprise only | Cost prohibitive |

**Implementation Notes**:
- Store Tushare token in environment variable
- Implement fallback logic: Tushare → AKShare on error
- Cache responses with 1-hour TTL
- Retry with exponential backoff (3 retries max)
- Monitor API quota usage to avoid limits

---

## Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **API Framework** | FastAPI | 0.110+ | Async REST API |
| **Data Validation** | Pydantic | 2.6+ | Request/response validation |
| **Database ORM** | SQLAlchemy | 2.0+ | Async database access |
| **Vector DB** | Qdrant | 1.10+ | Embeddings storage and search |
| **Relational DB** | PostgreSQL | 15+ | Structured data + pgvector |
| **Cache** | Redis | 7.2+ | Result caching |
| **Agent Framework** | LangGraph | 0.2+ | Agent orchestration |
| **LLM** | Claude 3.5 Sonnet | Latest | Reasoning and extraction |
| **Embeddings** | bge-m3 | Latest | Vector embeddings |
| **PDF Processing** | Unstructured.io | Latest | PDF to Markdown |
| **Financial Data** | Tushare Pro | Latest | Market and financial data |
| **Calculation** | Python | 3.11+ | Deterministic calculations |
| **Sandbox** | Docker | 24+ | Calculation isolation |
| **Testing** | pytest | 7.4+ | Test framework |
| **Type Checking** | mypy | 1.8+ | Static type checking |
| **Linting** | ruff | 0.1+ | Fast linter and formatter |

---

## Deployment Architecture

### Development Environment

```text
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  FastAPI     │  │  PostgreSQL   │  │  Qdrant   │ │
│  │  (Python)    │  │  + pgvector   │  │  (Vector) │ │
│  └──────┬───────┘  └──────────────┘  └───────────┘ │
│         │                                            │
│         │  ┌──────────────┐  ┌──────────────┐       │
│         └─→│    Redis     │  │  Calculation │       │
│            │   (Cache)    │  │  (Sandbox)   │       │
│            └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────┘
```

### Production Considerations (Post-MVP)

- Kubernetes deployment for scalability
- Nginx reverse proxy with SSL
- Prometheus + Grafana monitoring
- Sentry for error tracking
- GitHub Actions CI/CD pipeline
- Blue-green deployment strategy

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| LLM rate limits | Medium | High | Implement caching, fallback to DeepSeek, batch requests |
| Data source outage | Low | High | Dual data sources (Tushare + AKShare), 24h cached data grace period |
| Calculation errors | Low | Critical | Pure functions, property-based tests, audit trails |
| PDF parsing failures | Medium | Medium | Fallback to Marker, manual review pipeline |
| Token cost overruns | Medium | Medium | Hierarchical processing (small model for filtering, large for analysis) |
| Security vulnerabilities | Low | Critical | Sandbox isolation, input validation, regular security audits |

---

## Next Steps

Phase 0 complete. Proceed to Phase 1:

1. Create detailed [data-model.md](data-model.md) with all entities and relationships
2. Define API contracts in [contracts/](contracts/) directory
3. Write [quickstart.md](quickstart.md) for developers
4. Run `update-agent-context.sh` to update Claude Code context
5. Proceed to `/speckit.tasks` to generate implementation task breakdown
