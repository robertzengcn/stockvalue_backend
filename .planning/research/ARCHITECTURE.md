# Architecture Patterns

**Domain:** AI-enhanced value investment analysis platform (brownfield FastAPI)
**Researched:** 2026-04-14

## Recommended Architecture

The system extends its existing layered architecture (API -> Service -> Repository -> External/DB) with three new subsystems that sit at the Service layer. These subsystems are peers, not layers -- they communicate through shared state, not through each other.

```
                           FastAPI Application
                                   |
                          +--------+--------+
                          |   API Layer     |
                          | (routes + DI)   |
                          +--------+--------+
                                   |
                    +--------------+--------------+
                    |                             |
           +--------+--------+        +-----------+-----------+
           |  Orchestration   |        |   Direct Services     |
           |  (LangGraph)     |        |  (existing: risk,     |
           |  Coordinator ->  |        |   valuation, yield,   |
           |  Risk/Val/Yield  |        |   narrative)           |
           |  Agent nodes     |        +-----------+-----------+
           +--------+--------+                    |
                    |                    +--------+--------+
           +--------+--------+          |  Repository     |
           |   RAG Pipeline   |          |  Layer          |
           |  (PDF -> chunk ->|          +--------+--------+
           |   embed -> store |                   |
           |   -> retrieve)   |          +--------+--------+
           +--------+--------+          |   External /    |
                    |                    |   Database      |
           +--------+--------+          |  PostgreSQL +   |
           |   Cache Layer    |<-all----|  Redis + Qdrant |
           |  (Redis TTL)     |          +-----------------+
           +------------------+

Data Flow:
  Client -> Route -> [Coordinator Agent OR Direct Service]
    -> ExternalDataService (cached via Redis)
    -> [RAG Retrieve] -> Pure Calculation
    -> Narrative Generation -> Repository -> PostgreSQL
```

### Component Boundaries

| Component | Responsibility | Communicates With | Owns |
|-----------|---------------|-------------------|------|
| **API Layer** | HTTP I/O, request validation, response envelope | Services, Agents, DI container | Routes, request/response models |
| **Coordinator Agent** | LangGraph StateGraph: routes requests to specialized agents, manages shared state | Risk/Valuation/Yield Agent nodes, RAG Retriever, ExternalDataService | Graph definition, AgentState TypedDict |
| **Risk Agent Node** | LangGraph node: orchestrates risk analysis, calls M-Score calculation + RAG retrieval | Coordinator (via state), RiskService (pure), RAG Retriever | Risk-specific prompts, tool definitions |
| **Valuation Agent Node** | LangGraph node: orchestrates DCF valuation, retrieves research report data | Coordinator (via state), ValuationService (pure), RAG Retriever | Valuation-specific prompts |
| **Yield Agent Node** | LangGraph node: orchestrates yield gap analysis, fetches live rates | Coordinator (via state), YieldService (pure), ExternalDataService | Yield-specific prompts |
| **RAG Pipeline** | PDF upload -> Markdown -> chunk -> embed -> store in Qdrant -> retrieve | API Layer (upload endpoint), Agent nodes (retrieval calls) | PDF processor, chunker, embedder, Qdrant client, retriever |
| **Cache Layer** | Transparent Redis TTL caching for external data and computation results | ExternalDataService, Route handlers (via decorator) | CacheManager, TTL policies, invalidation rules |
| **Pure Calculation Services** | Stateless financial math (M-Score, DCF, yield gap, F-Score) | Agent nodes, Route handlers (existing) | No state -- pure functions only |
| **Narrative Service** | LLM narrative generation with graceful fallback | Agent nodes, Route handlers (existing) | LLM client, prompt templates |
| **Repository Layer** | Database CRUD, query construction | Services, Agent nodes | SQLAlchemy sessions, ORM models |
| **External Data Service** | Multi-source data fetching with fallback chain | Cache Layer (wraps calls), Agent nodes | AKShare/efinance/Tushare clients |

### Data Flow

**Flow 1: Comprehensive Analysis (new multi-agent path)**

```
Client -> POST /api/v1/analyze/comprehensive
  -> Coordinator Agent (LangGraph StateGraph)
    -> Router node: classify request -> dispatch to agent nodes
    -> [Risk Agent Node]
      -> ExternalDataService.get_financial_report (cached)
      -> RiskService.calculate_beneish_m_score (pure)
      -> RAG Retriever: search annual report for MD&A context
      -> Narrative generation
      -> Update shared state with risk results
    -> [Valuation Agent Node]
      -> ExternalDataService.get_financial_report (cached)
      -> ValuationService.calculate_dcf (pure)
      -> RAG Retriever: search research reports for growth assumptions
      -> Narrative generation
      -> Update shared state with valuation results
    -> [Yield Agent Node]
      -> ExternalDataService.get_price + get_rate (cached)
      -> YieldService.calculate_yield_gap (pure)
      -> Narrative generation
      -> Update shared state with yield results
    -> Synthesis node: aggregate all agent results
  -> Persist all results via repositories
  -> Return ApiResponse[ComprehensiveAnalysis]
```

**Flow 2: Single Analysis (existing direct path, enhanced with cache)**

```
Client -> POST /api/v1/analyze/risk
  -> Route handler checks Redis cache (key: "risk:{ticker}:{year}")
  -> Cache miss -> ExternalDataService.get_financial_report (also cached)
  -> RiskService.analyze (pure function, no cache needed)
  -> NarrativeService.generate_narrative (LLM call)
  -> Persist via RiskScoreRepository
  -> Cache result with TTL 86400s (financial data changes daily at most)
  -> Return ApiResponse[RiskScoreWithNarrative]
```

**Flow 3: RAG Document Ingestion (new)**

```
Client -> POST /api/v1/documents/upload (PDF + metadata)
  -> PDF Processor: Marker/Unstructured.io -> Markdown
  -> Chunker: split by Markdown headers, then RecursiveCharacterTextSplitter
    -> Parent chunks: ~2000 tokens (preserve section context)
    -> Child chunks: ~512 tokens (for embedding-based search)
  -> Embedder: FastEmbed with bge-m3 -> dense + sparse vectors
  -> Qdrant: store child chunks with parent_id metadata
  -> PostgreSQL: store document metadata (ticker, year, report_type)
  -> Return ApiResponse[DocumentIngestionResult]
```

**Flow 4: RAG Retrieval (called by agent nodes)**

```
Agent Node calls RAGRetriever.retrieve(query, filters)
  -> Embed query with bge-m3
  -> Qdrant hybrid search (dense + sparse) with metadata filters
    -> Pre-filter: ticker, year, report_type (from PostgreSQL metadata)
    -> Search: top-k child chunks by similarity
  -> Fetch parent chunks for each hit (parent-document retrieval)
  -> Return: list of parent chunk texts with source metadata
```

## Patterns to Follow

### Pattern 1: LangGraph StateGraph for Multi-Agent Orchestration

**What:** A directed state graph where each node is an agent step, and edges control flow based on state conditions.

**When:** Any analysis request that involves multiple analysis types or requires data from RAG + external sources + calculations in a coordinated workflow.

**Why LangGraph over raw LangChain:** The project already depends on `langgraph>=1.0.9` and `langchain>=1.2.10`. LangGraph provides explicit state management, conditional edges, and cycle support (for retry/validation loops) that raw LangChain chains lack. The project's doc explicitly calls for "LangGraph-based state machine for multi-step analysis with validation loops."

**Example:**
```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class AnalysisState(TypedDict, total=False):
    ticker: str
    year: int
    financial_data: dict  # from ExternalDataService (cached)
    rag_context: list[str]  # from RAG retriever
    risk_result: dict | None
    valuation_result: dict | None
    yield_result: dict | None
    narrative: str | None
    errors: list[str]


def route_analysis(state: AnalysisState) -> str:
    """Conditional edge: decide which agents to run."""
    # For comprehensive analysis, run all three in sequence
    return "risk_analysis"


async def risk_analysis_node(state: AnalysisState) -> dict:
    """Risk agent node: fetch data, calculate, retrieve RAG context."""
    from stockvaluefinder.services.risk_service import analyze_financial_risk
    from stockvaluefinder.rag.retriever import RAGRetriever

    # Pure calculation (deterministic, no LLM)
    risk_score = analyze_financial_risk(
        state["financial_data"]["current"],
        state["financial_data"]["previous"],
    )

    # RAG retrieval for context enrichment (optional enhancement)
    retriever = RAGRetriever()
    rag_context = await retriever.retrieve(
        query=f"{state['ticker']} risk factors fraud",
        filters={"ticker": state["ticker"], "year": state["year"]},
    )

    return {
        "risk_result": risk_score.model_dump(),
        "rag_context": rag_context,
    }


# Build the graph
graph = StateGraph(AnalysisState)
graph.add_node("risk_analysis", risk_analysis_node)
graph.add_node("valuation_analysis", valuation_analysis_node)
graph.add_node("yield_analysis", yield_analysis_node)
graph.add_node("synthesis", synthesis_node)

graph.add_edge(START, "risk_analysis")
graph.add_edge("risk_analysis", "valuation_analysis")
graph.add_edge("valuation_analysis", "yield_analysis")
graph.add_edge("yield_analysis", "synthesis")
graph.add_edge("synthesis", END)

coordinator = graph.compile()
```

**Key design rule:** Agent nodes call pure calculation services and RAG retrieval. LLMs are used only for narrative generation and result interpretation -- never for arithmetic. This preserves the project's "deterministic agent architecture" principle.

### Pattern 2: Parent-Document Retrieval for Financial RAG

**What:** Split documents into small child chunks for precise embedding search, but return larger parent chunks to provide the LLM with full section context.

**When:** Processing 200+ page annual reports where individual paragraphs lose meaning without section context.

**Why:** The project doc explicitly specifies "Parent-Document Retrieval: 500-token chunks for search, return 2000-token parent context." This is the established best practice for financial documents where context (section headings, table context) matters as much as content.

**Example:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition


class RAGDocumentStore:
    """Store and retrieve financial documents with parent-child chunking."""

    def __init__(self, qdrant_client: QdrantClient, embedder: Any) -> None:
        self._client = qdrant_client
        self._embedder = embedder

    async def store_document(
        self,
        ticker: str,
        year: int,
        chunks: list[dict],  # each has text, parent_id, metadata
    ) -> None:
        """Embed child chunks and store in Qdrant with parent reference."""
        points = []
        for i, chunk in enumerate(chunks):
            vector = self._embedder.embed(chunk["text"])
            points.append(PointStruct(
                id=f"{ticker}_{year}_{chunk['parent_id']}_{i}",
                vector=vector,
                payload={
                    "text": chunk["text"],
                    "parent_text": chunk.get("parent_text", ""),
                    "parent_id": chunk["parent_id"],
                    "ticker": ticker,
                    "year": year,
                    "section": chunk.get("section", ""),
                },
            ))
        self._client.upsert(collection_name="annual_reports", points=points)

    async def retrieve(
        self,
        query: str,
        filters: dict,
        top_k: int = 5,
    ) -> list[str]:
        """Search child chunks, return parent context."""
        query_vector = self._embedder.embed(query)
        results = self._client.search(
            collection_name="annual_reports",
            query_vector=query_vector,
            query_filter=Filter(must=[
                FieldCondition(key="ticker", match={"value": filters["ticker"]}),
                FieldCondition(key="year", match={"value": filters["year"]}),
            ]),
            limit=top_k,
        )
        # Return unique parent chunks
        seen_parents = set()
        parent_texts = []
        for hit in results:
            parent_id = hit.payload["parent_id"]
            if parent_id not in seen_parents:
                seen_parents.add(parent_id)
                parent_texts.append(hit.payload["parent_text"])
        return parent_texts
```

### Pattern 3: Transparent Cache Integration via Dependency Injection

**What:** Cache external data calls transparently using FastAPI dependency injection, not by modifying the ExternalDataService itself.

**When:** All external data calls that are expensive and have predictable freshness requirements.

**Why:** The existing `CacheManager` in `utils/cache.py` (292 lines) is fully implemented with `cache_result` and `invalidate_cache` decorators. The `get_cache()` dependency in `dependencies.py` exists but yields `None`. The integration gap is in the DI wiring, not the cache implementation.

**Example (integration approach):**
```python
# In dependencies.py -- wire up the existing CacheManager
from stockvaluefinder.utils.cache import CacheManager

_cache_manager: CacheManager | None = None

async def get_cache() -> AsyncGenerator[CacheManager, None]:
    """Provide initialized CacheManager via DI."""
    global _cache_manager
    if _cache_manager is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _cache_manager = CacheManager(redis_url)
        await _cache_manager.connect()
    yield _cache_manager
```

**TTL Policy (from project requirements):**
| Data Type | TTL | Cache Key Pattern |
|-----------|-----|-------------------|
| Financial reports | 86400s (24h) | `financial:{ticker}:{year}` |
| Stock prices | 300s (5min) | `price:{ticker}` |
| Interest rates | 3600s (1h) | `rate:{type}` |
| Analysis results | 86400s (24h) | `analysis:{type}:{ticker}:{year}` |

### Pattern 4: Subprocess Calculation Sandbox

**What:** Execute Python calculation code in a subprocess with resource limits, not in the main process.

**When:** Any calculation that comes from or is influenced by external data, to prevent a malformed input from crashing the server.

**Why:** The project explicitly calls for a subprocess sandbox. The existing `calculation_sandbox.py` is a 27-line TODO stub. For MVP, a subprocess with timeout and memory limits is sufficient (Docker sandbox is out of scope per PROJECT.md).

**Example:**
```python
import asyncio
import json
import subprocess


async def execute_calculation(
    code: str,
    timeout: int = 30,
    max_memory_mb: int = 256,
) -> dict:
    """Run Python code in a subprocess with resource limits.

    Args:
        code: Python code to execute (must print JSON to stdout)
        timeout: Maximum execution time in seconds
        max_memory_mb: Memory limit in MB

    Returns:
        Parsed JSON result from subprocess stdout
    """
    try:
        result = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            result.communicate(), timeout=timeout
        )
        if result.returncode != 0:
            raise CalculationError(f"Sandbox error: {stderr.decode()}")
        return json.loads(stdout.decode())
    except asyncio.TimeoutError:
        raise CalculationError(f"Calculation timed out after {timeout}s")
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: LLM Doing Arithmetic

**What:** Passing raw numbers to the LLM and asking it to compute M-Score, DCF, or yield gap values.

**Why bad:** LLMs hallucinate arithmetic. A single wrong digit in a financial calculation destroys user trust and creates liability. The project's core principle is "LLMs handle understanding, Python/SQL handles calculations."

**Instead:** Agent nodes extract parameters from data (via code, not LLM), pass them to pure Python calculation services, then use LLMs only to narrate the pre-computed results.

### Anti-Pattern 2: Fat Route Handlers

**What:** Putting orchestration logic, data fetching, calculation, narrative generation, and persistence all in a single route handler function.

**Why bad:** The existing risk_routes.py (149 lines) already shows this pattern -- a single function fetches data, analyzes, generates narrative, saves to DB. This makes testing impossible without spinning up the entire FastAPI app.

**Instead:** Route handlers should be thin: validate input, delegate to an orchestrator (agent graph or service), format response. For the multi-agent path, the route handler calls `coordinator.ainvoke(state)` and the graph handles the rest.

### Anti-Pattern 3: Synchronous LLM Calls in Async Routes

**What:** Using `llm.invoke()` instead of `llm.ainvoke()` inside async FastAPI route handlers.

**Why bad:** Blocks the event loop, killing FastAPI's concurrency. LLM calls take 2-10 seconds; blocking during that time prevents other requests from being served.

**Instead:** Always use `await llm.ainvoke()` or `async for chunk in graph.astream()`. The existing NarrativeService already does this correctly with `await llm.ainvoke(messages)`.

### Anti-Pattern 4: Embedding Model Download at Request Time

**What:** Loading bge-m3 model weights on the first RAG retrieval request.

**Why bad:** bge-m3 is ~2GB. Downloading/loading it during a user request causes a 30-60 second delay or timeout.

**Instead:** Load the embedding model during FastAPI lifespan startup (in the `lifespan()` function in main.py). Warm up with a dummy embedding to ensure the model is fully loaded before accepting requests.

### Anti-Pattern 5: Tight Coupling Between Agents and Data Sources

**What:** Each agent directly importing and calling AKShareClient or efinance_client.

**Why bad:** The ExternalDataService facade exists precisely to abstract the fallback chain. Agents should not bypass it.

**Instead:** Agent nodes receive `ExternalDataService` via dependency injection (through the graph state or constructor). The facade handles fallback, caching, and error recovery.

## Build Order (Dependency Analysis)

The components have a clear dependency chain that dictates build order:

```
Phase 1: M-Score Index Calculation (no new infrastructure)
  |
  v
Phase 2: Redis Cache Integration (existing CacheManager, just wire it)
  |
  v
Phase 3: RAG Pipeline (new Qdrant + embeddings infrastructure)
  |
  v
Phase 4: Multi-Agent Orchestration (depends on all above)
```

**Rationale:**

1. **M-Score calculation first** because it fixes existing broken behavior (hardcoded defaults returning meaningless results). It requires no new infrastructure -- just extracting the 8 raw financial indices from the data already fetched by ExternalDataService. This is a pure refactoring of `risk_service.py` with no new dependencies.

2. **Redis cache second** because the `CacheManager` (292 lines) is already implemented. Integration requires: (a) wiring `get_cache()` in dependencies.py, (b) adding cache checks to route handlers or wrapping ExternalDataService calls, (c) adding Redis URL to config. This is integration work, not new development.

3. **RAG pipeline third** because it introduces new infrastructure (Qdrant, embedding model, PDF processing). The RAG pipeline must work standalone before agents can use it for context enrichment. This phase includes: PDF upload endpoint, chunking pipeline, Qdrant collection setup, embedding model loading, retrieval endpoint.

4. **Multi-agent orchestration last** because it depends on everything above: it needs working calculations (Phase 1), cached data access (Phase 2), and RAG retrieval (Phase 3). Building it first would require mocking all three, leading to integration problems later.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| External API rate limits | Single AKShare instance handles easily | Add request queuing, increase cache TTL, batch requests | Dedicated data pipeline, pre-compute CSI 300 reports nightly |
| LLM cost (narrative generation) | ~$0.01 per analysis (DeepSeek) | ~$100/day -- acceptable for premium tool | Cache narratives, batch generate, use smaller model for updates |
| Qdrant vector storage | Single Qdrant container, CSI 300 annual reports (~600 docs) | Same -- CSI 300 scope is bounded | Sharded Qdrant cluster, index optimization |
| Redis cache | Single Redis instance | Redis with persistence, monitor hit rates | Redis Cluster, CDN for static reports |
| PostgreSQL | Single instance with connection pool | Read replicas for analysis queries | Partitioned tables by year, materialized views for aggregates |
| Concurrent analysis requests | FastAPI async handles 100 concurrent | Add request queue, limit concurrent LLM calls | Dedicated worker pool, background job processing |

**Key insight:** CSI 300 is a bounded dataset. There are exactly 300 stocks, each with at most 10 years of annual reports. Total documents: ~3000 annual reports. Total vectors: ~60,000 chunks (20 chunks per report * 3000 reports). This is tiny for Qdrant and PostgreSQL. Scaling concerns are about concurrent users, not data volume.

## Component Integration Details

### LangGraph State Design

The shared state (`AnalysisState`) is the single source of truth flowing through the graph. Each agent node reads from and writes to this state. The state should use `TypedDict` (not Pydantic) for LangGraph compatibility.

```python
class AnalysisState(TypedDict, total=False):
    # Input
    ticker: str
    year: int
    analysis_types: list[str]  # ["risk", "valuation", "yield"]

    # Shared data (populated by data_fetch node)
    financial_data: dict
    current_price: float
    interest_rates: dict

    # Agent results (each agent writes to its own key)
    risk_result: dict
    valuation_result: dict
    yield_result: dict

    # RAG context (populated by retrieval node or within agents)
    rag_context: list[str]

    # Final output
    narrative: str
    errors: list[str]
```

### FastAPI Lifespan Integration

The `lifespan()` function in `main.py` currently has four TODOs. It should be updated to initialize all infrastructure:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # 1. Initialize Redis cache
    cache_manager = CacheManager(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    await cache_manager.connect()
    app.state.cache = cache_manager

    # 2. Initialize Qdrant client
    from qdrant_client import AsyncQdrantClient
    qdrant = AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    app.state.qdrant = qdrant

    # 3. Warm up embedding model (loads bge-m3, ~2GB)
    from stockvaluefinder.rag.embeddings import EmbeddingService
    embedder = EmbeddingService()
    await embedder.warmup()  # dummy embed to load model
    app.state.embedder = embedder

    # 4. Initialize coordinator agent graph
    from stockvaluefinder.agents.coordinator import build_coordinator_graph
    app.state.coordinator = build_coordinator_graph()

    yield

    # Shutdown
    await cache_manager.disconnect()
    await qdrant.close()
```

### Where Agents Fit in the Layered Architecture

Agents are NOT a new layer. They sit at the Service layer level, orchestrating calls to existing services:

```
API Layer (routes)
  |
  +---> Direct Service call (existing path: risk_routes -> RiskService)
  |
  +---> Agent Graph call (new path: agent_routes -> Coordinator Graph)
          |
          +---> Risk Agent Node -> RiskService (pure function)
          +---> Valuation Agent Node -> ValuationService (pure function)
          +---> Yield Agent Node -> YieldService (pure function)
          +---> RAG Retrieve -> RAGRetriever
          +---> Narrative -> NarrativeService
```

The existing single-analysis routes remain untouched. The new comprehensive analysis route adds alongside them.

### New Files to Create

```
stockvaluefinder/
  api/
    agent_routes.py         # POST /api/v1/analyze/comprehensive
    document_routes.py      # POST /api/v1/documents/upload, GET /api/v1/documents/search
  agents/
    coordinator.py          # LangGraph StateGraph builder + AnalysisState TypedDict
    risk_agent.py           # Risk agent node function
    valuation_agent.py      # Valuation agent node function
    yield_agent.py          # Yield agent node function
    prompts.py              # Agent-specific system prompts (separate from narrative_prompts.py)
  rag/
    pdf_processor.py        # PDF -> Markdown conversion (Marker or Unstructured.io)
    chunker.py              # Parent-child chunking with Markdown header splitting
    embeddings.py           # FastEmbed bge-m3 wrapper with warmup
    vector_store.py         # Qdrant collection management, upsert, search
    retriever.py            # High-level retrieve(query, filters) -> list[str]
  services/
    mscore_calculator.py    # Extract 8 M-Score indices from raw financial data (new)
    calculation_sandbox.py  # Subprocess execution (refactor from TODO stub)
```

### Existing Files to Modify

| File | Change | Risk |
|------|--------|------|
| `main.py` | Update lifespan to init Redis, Qdrant, embedder | LOW (additive) |
| `config.py` | Add RAGConfig, CacheConfig dataclasses | LOW (additive) |
| `dependencies.py` | Wire `get_cache()` to real CacheManager | LOW (single function) |
| `risk_service.py` | Replace hardcoded M-Score indices with calculated values | MEDIUM (core logic change, must maintain backward compat) |
| `pyproject.toml` | Add `fastembed`, `marker-pdf` or `unstructured` | LOW (dependencies) |

## Sources

- [AWS Blog: Build an intelligent financial analysis agent with LangGraph](https://aws.amazon.com/blogs/machine-learning/build-an-intelligent-financial-analysis-agent-with-langgraph-and-strands-agents/) -- HIGH confidence: LangGraph + financial analysis architecture patterns
- [LangGraph Graph API Overview (Official Docs)](https://docs.langchain.com/oss/python/langgraph/graph-api) -- HIGH confidence: StateGraph, TypedDict state, conditional edges
- [Qdrant Hybrid Search with FastEmbed](https://qdrant.tech/documentation/tutorials-search-engine-engineering/hybrid-search-fastembed/) -- HIGH confidence: bge-m3 + Qdrant integration patterns
- [FastEmbed: Qdrant's Efficient Python Library](https://qdrant.tech/articles/fastembed/) -- HIGH confidence: embedding generation without heavy ML dependencies
- [Parent Document Retrieval (LanceDB)](https://www.lancedb.com/blog/modified-rag-parent-document-bigger-chunk-retriever-62b3d1e79bc6) -- MEDIUM confidence: PDR pattern with token sizing (512 child / 2048 parent)
- [FastAPI + LangGraph Production Template (GitHub)](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template) -- MEDIUM confidence: FastAPI async + LangGraph integration patterns
- [fastapi-cache (GitHub)](https://github.com/long2ice/fastapi-cache) -- MEDIUM confidence: decorator-based caching for FastAPI
- [Reddit: Best Chunking Strategy for Financial Reports](https://www.reddit.com/r/Rag/comments/1mjwde9/best_chunking_strategy_for_rag_on_annualfinancial/) -- LOW confidence: community discussion on financial PDF chunking
- Project codebase analysis (ARCHITECTURE.md, STRUCTURE.md, existing source code) -- HIGH confidence: direct observation of existing patterns
