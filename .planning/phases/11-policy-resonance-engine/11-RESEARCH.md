# Phase 11: Policy Resonance Engine - Research

**Researched:** 2026-05-06
**Domain:** Semantic policy-stock matching with RAG pipeline integration
**Confidence:** HIGH

## Summary

Phase 11 builds a Policy Resonance Engine that uploads policy PDF documents, stores them in a dedicated Qdrant collection (`policy_documents`), vector-matches policy text against stock business descriptions, uses DeepSeek LLM to verify matches and reduce false positives, produces a 0-100 resonance score, and auto-adjusts DCF terminal growth rate based on resonance tier.

**Primary recommendation:** Reuse the existing RAG pipeline (QdrantVectorStore, BGEEmbeddingClient, pdf_processor) almost entirely. The critical discovery is that `stock_individual_info_em()` does NOT return business descriptions -- use `stock_profile_cninfo(symbol='600519')` instead, which returns both `主营业务` and `经营范围` fields. Cross-collection Qdrant search works naturally since both collections use the same BGE-M3 1024-dim COSINE vectors.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Policy PDF upload and storage | API / Backend | Database / Storage | FastAPI endpoint receives PDF, Qdrant stores vectors, filesystem stores file |
| Policy document chunking | Backend | -- | pdf_processor.py pure functions handle this |
| Stock business description fetch | API / Backend | CDN / Static (Redis cache) | AKShare API call + Redis cache |
| Vector similarity matching | Backend (Qdrant) | -- | Qdrant handles COSINE search, same 1024-dim vectors across collections |
| LLM match verification | Backend (DeepSeek) | -- | DeepSeek via existing llm_factory.py, same pattern as NarrativeService |
| Resonance score calculation | Backend (pure function) | -- | Stateless pure function in policy_service.py |
| DCF terminal growth adjustment | Backend (pure function) | -- | Clamps within ValuationConfig bounds |
| API response composition | API / Backend | -- | FastAPI route orchestrates all layers |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Stock business descriptions sourced from AKShare `stock_individual_info_em()` (经营范围/主营业务 field). Add `business_description` column to `StockDB` model. Fetch + cache per stock with Redis TTL consistent with existing patterns.
- **D-02:** Top 5 policy document chunks matched per stock for broader coverage across multi-domain policies. Returns top 5 most relevant matched excerpts with scores.
- **D-03:** LLM (DeepSeek) classification used to verify matches and reduce false positives after vector similarity search. Vector similarity finds candidate matches, LLM confirms true relevance per ROADMAP POL-02.
- **D-04:** Weighted formula for resonance score (0-100): `60% * (avg_cosine_similarity * 100) + 40% * (avg_llm_confidence * 100)`. Only verified-relevant matches (LLM `relevant=true`) contribute to the score. If no relevant matches found, score = 0.
- **D-05:** LLM returns structured verdict per match: `{relevant: bool, confidence: float 0-1, reason: string}`. Confidence feeds into score formula, relevant flag filters non-matches. Reason included in API response for audit trail.
- **D-06:** Resonance threshold of 40/100 to qualify as 'policy-aligned' for DCF adjustment purposes.
- **D-07:** Tiered DCF terminal growth adjustment based on resonance score: Strongly Supportive (>=80, +1.5%), Supportive (40-79, +1.0%), Neutral (<40, 0%). No negative adjustment.
- **D-08:** Hard cap on terminal growth adjustment at +1.5%. Subject to existing `ValuationConfig.MAX_TERMINAL_GROWTH = 10%` absolute cap.
- **D-09:** Combined API response: resonance score, tier label, matched policy excerpts, DCF adjustment details (adjustment_pct, adjusted_terminal_growth, original_terminal_growth) returned in single endpoint call.
- **D-10:** Enriched metadata per policy document: title, upload_date, policy_type (industry/fiscal/monetary/trade), issuing_body (国务院/证监会/发改委/etc), effective_date, industry_tags. LLM auto-extracts these from document content during upload processing.
- **D-11:** Match ALL uploaded policy documents against a stock when requesting resonance analysis. No pre-selection needed.
- **D-12:** Separate Qdrant collection named `policy_documents` with its own payload indexes (policy_type, issuing_body, effective_date).

### Claude's Discretion
- Exact AKShare method name and field mapping for business descriptions (verify `stock_individual_info_em()` availability)
- Policy upload API endpoint path and request/response models
- New ORM model field names and Alembic migration details
- LLM prompt engineering for match verification and metadata extraction
- Internal function organization within policy_service.py
- Test file structure and test case selection

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POL-01 | User can upload policy documents (PDF) which are stored in a dedicated Qdrant collection with policy metadata | Reuse pdf_processor.py for chunking, QdrantVectorStore with `collection="policy_documents"`, LLM metadata extraction from document content |
| POL-02 | System matches policy documents to stocks via vector similarity (policy text vs stock business description) with LLM classification to reduce false positives | BGEEmbeddingClient generates query vector from stock business description, QdrantVectorStore.search() on policy_documents collection, DeepSeek verifies matches |
| POL-03 | User can view policy resonance score per stock (0-100) with matched policy excerpts | Pure function in policy_service.py implements D-04 formula, returns top 5 matches with scores and LLM reasons |
| POL-04 | System auto-adjusts DCF terminal growth rate based on policy resonance (supportive policy -> +1% adjustment) | Pure function calculates adjustment per D-07 tiers, clamps per D-08 and ValuationConfig bounds |
</phase_requirements>

## Critical Discovery: AKShare Business Description API

**D-01 states `stock_individual_info_em()`**, but this function does NOT return business descriptions. Verified by running the actual API call:

```
stock_individual_info_em(symbol='600519') returns:
  item: 最新, 股票代码, 股票简称, 总股本, 流通股, 总市值, 流通市值, 行业, 上市时间
```

**The correct function is `stock_profile_cninfo(symbol='600519')`** which returns 26 columns including:

| Field | Example (600519) |
|-------|-----------------|
| `主营业务` | 贵州茅台酒系列产品的产品研制、酿造生产、包装和销售。 |
| `经营范围` | 茅台酒系列产品的生产与销售；饮料、食品、包装材料的生产、销售；... |
| `所属行业` | 酒、饮料和精制茶制造业 |
| `A股代码` | 600519 |
| `A股简称` | 贵州茅台 |

Verified with both `600519` (Moutai) and `000002` (Vanke). The function accepts 6-digit stock codes (not ts_code format). [VERIFIED: runtime test on 2026-05-06, AKShare 1.18.46]

**Recommendation:** Use `主营业务` as the primary business description for embedding. If it is too short (e.g., "房地产、贸易及零售等。" for 000002), concatenate with `经营范围` for richer semantic matching.

## Standard Stack

### Core (No new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| qdrant-client | 1.17.0 | Vector storage and search | Already installed, used by existing QdrantVectorStore |
| httpx | >=0.27.0 | HTTP client for embedding API | Already installed, used by BGEEmbeddingClient |
| akshare | 1.18.46 | Stock business descriptions | Already installed, `stock_profile_cninfo()` verified |
| langchain-openai | >=1.1.12 | DeepSeek LLM via ChatOpenAI | Already installed, used by llm_factory.py |
| pymupdf | >=1.27.2.2 | PDF text extraction | Already installed, used by pdf_processor.py |
| tiktoken | >=0.12.0 | Token counting for chunking | Already installed, used by pdf_processor.py |
| redis | >=7.2.1 | Caching business descriptions | Already installed, used by CacheManager |
| fastapi | >=0.133.1 | API endpoints | Already installed |
| pydantic | >=2.12.5 | Request/response models | Already installed |
| sqlalchemy | >=2.0.47 | ORM models | Already installed |
| alembic | >=1.18.4 | Database migrations | Already installed |

### No New Dependencies Required

All functionality can be built using existing project dependencies. No `uv add` needed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `stock_profile_cninfo` | `stock_individual_info_em` + manual web scrape | web scraping unreliable, cninfo is official data source |
| Separate embedding model for policy text | Same BGE-M3 for both | BGE-M3 handles Chinese text well, consistency enables cross-collection search |
| Store business descriptions only in DB | Store in DB + Redis cache | Cache avoids repeated AKShare calls; DB provides persistence |

## Architecture Patterns

### System Architecture Diagram

```
[Policy PDF Upload]
       |
       v
[pdf_processor.extract_pdf_content()]  -- Reuse existing
       |
       v
[pdf_processor.chunk_into_parents() + chunk_parents_into_children()]  -- Reuse existing
       |
       v
[LLM: Extract policy metadata (title, type, issuing_body, effective_date)]
       |
       v
[BGEEmbeddingClient.generate_embeddings()]  -- Reuse existing, same 1024-dim vectors
       |
       v
[QdrantVectorStore(collection="policy_documents").upsert_chunks()]  -- New collection


[Stock Resonance Request: ticker]
       |
       v
[AKShareClient: stock_profile_cninfo(symbol=ticker)]  -- NEW method
       |  -> returns 主营业务 + 经营范围
       v
[Redis Cache: v1:business_description:{ticker}]  -- Cache with 24h TTL
       |
       v
[BGEEmbeddingClient.generate_query_embedding(description)]  -- Reuse existing
       |  -> 1024-dim query vector
       v
[QdrantVectorStore(collection="policy_documents").search(query_vector, limit=5)]
       |  -> Top 5 policy chunks with cosine similarity scores
       v
[LLM (DeepSeek): Verify each match -> {relevant, confidence, reason}]
       |  -> Filter: only relevant=true matches continue
       v
[policy_service: Calculate resonance score per D-04]
       |  -> 60% * avg_cosine * 100 + 40% * avg_confidence * 100
       v
[policy_service: Determine DCF adjustment per D-07, D-08]
       |  -> Tier: >=80 -> +1.5%, 40-79 -> +1.0%, <40 -> 0%
       v
[Combined API Response: score + tier + excerpts + DCF adjustment]
```

### Recommended Project Structure

```
stockvaluefinder/
├── api/
│   └── policy_routes.py              # NEW: Upload + resonance endpoints
├── services/
│   └── policy_service.py             # NEW: Pure functions (score, adjustment, verification)
├── models/
│   └── policy.py                     # NEW: Pydantic models for policy domain
├── db/models/
│   └── policy.py                     # NEW: PolicyDocumentDB ORM model
├── repositories/
│   └── policy_repo.py                # NEW: PolicyRepository
├── external/
│   ├── akshare_client.py             # MODIFY: Add get_stock_business_description()
│   └── data_service.py               # MODIFY: Add get_business_description() with cache
├── rag/
│   ├── vector_store.py               # REUSE: Instantiate with collection="policy_documents"
│   ├── embeddings.py                 # REUSE: BGEEmbeddingClient unchanged
│   └── pdf_processor.py              # REUSE: extract_pdf_content, chunk functions unchanged
├── config.py                         # MODIFY: Add PolicyResonanceConfig
├── alembic/versions/
│   └── 013_policy_tables.py          # NEW: Migration for policy tables + stock.business_description
└── main.py                           # MODIFY: Register policy_router
```

### Pattern 1: Cross-Collection Qdrant Search
**What:** Use a vector from one Qdrant collection to search another collection.
**When to use:** Searching policy documents using stock business description as query.
**How it works:** Both collections use the same BGE-M3 model producing 1024-dim COSINE vectors. The vector space is identical regardless of which collection generated the vector. Simply generate a query embedding from stock description, then call `search()` on the `policy_documents` collection with that vector.

```python
# Instantiate vector store for policy collection
policy_store = QdrantVectorStore(
    url=rag_config.QDRANT_URL,
    collection="policy_documents",  # Different collection name
    embedding_client=embedding_client,
)

# Generate query vector from stock business description
query_vector = await embedding_client.generate_query_embedding(business_description)

# Search policy_documents using stock description vector -- works because same embedding model
results = await policy_store.search(
    query_vector=query_vector,
    limit=5,              # D-02: Top 5 chunks
    score_threshold=0.5,  # Lower threshold, LLM will filter false positives
)
```

### Pattern 2: LLM Structured Output for Match Verification
**What:** Use DeepSeek to verify vector similarity matches and return structured `{relevant, confidence, reason}`.
**When to use:** After vector search returns candidate policy-stock matches.
**Pattern:** Same as NarrativeService -- lazy LLM init, try/except with graceful fallback.

```python
# Source: follows narrative_service.py pattern
PROMPT_TEMPLATE = """你是一位政策分析专家。判断以下政策文本片段是否与该公司的主营业务相关。

公司主营业务：{business_description}
政策文本片段：{policy_chunk}

请严格按以下JSON格式回复：
{{"relevant": true/false, "confidence": 0.0-1.0, "reason": "简要说明"}}

判断标准：
1. relevant=true 仅当政策直接涉及该公司的核心业务领域
2. confidence 反映你对该判断的确信程度
3. reason 用一句中文解释判断依据"""
```

### Pattern 3: LLM Metadata Extraction from Policy Documents
**What:** During upload, extract structured metadata from policy PDF content.
**When to use:** After PDF text extraction, before Qdrant upsert.

```python
METADATA_PROMPT = """从以下政策文档内容中提取结构化信息。返回纯JSON格式：
{{"title": "政策标题", "policy_type": "industry/fiscal/monetary/trade",
  "issuing_body": "发文机构", "effective_date": "YYYY-MM-DD或null",
  "industry_tags": ["行业标签1", "行业标签2"]}}

文档内容（前2000字）：
{content}"""
```

### Pattern 4: Frozen Config Dataclass for Policy Resonance
**What:** Configuration constants for policy matching thresholds.
**When to use:** In config.py, following existing ValuationConfig, ROICConfig pattern.

```python
@dataclass(frozen=True)
class PolicyResonanceConfig:
    """Configuration for policy resonance analysis."""
    MATCH_LIMIT: int = 5                  # D-02: Top 5 chunks
    COSINE_WEIGHT: float = 0.60           # D-04: 60% cosine similarity
    LLM_WEIGHT: float = 0.40              # D-04: 40% LLM confidence
    RESONANCE_THRESHOLD: float = 40.0     # D-06: Score threshold for DCF
    STRONG_TIER_THRESHOLD: float = 80.0   # D-07: Strongly Supportive tier
    STRONG_ADJUSTMENT: float = 0.015      # D-07: +1.5%
    MODERATE_ADJUSTMENT: float = 0.01     # D-07: +1.0%
    NEUTRAL_ADJUSTMENT: float = 0.0       # D-07: 0%
    MAX_ADJUSTMENT_CAP: float = 0.015     # D-08: Hard cap +1.5%
    VECTOR_SEARCH_THRESHOLD: float = 0.5  # Lower than RAG's 0.7, LLM filters false positives
    BUSINESS_DESC_CACHE_TTL: int = 86400  # 24h cache for business descriptions
```

### Anti-Patterns to Avoid
- **Using `stock_individual_info_em()` for business descriptions:** It does NOT return 经营范围/主营业务. Use `stock_profile_cninfo()` instead. [VERIFIED: runtime test]
- **Creating a separate embedding model for policy text:** Must use the same BGE-M3 model so cross-collection vector search works. [VERIFIED: both collections share 1024-dim COSINE vectors]
- **Storing policy chunks with stock-specific metadata:** Policy documents are not stock-specific. Store with policy metadata only (document_id, policy_type, issuing_body, effective_date). [CITED: CONTEXT.md D-12]
- **Running LLM verification on ALL search results:** Only verify top-N (5) candidates to control API costs. [CITED: CONTEXT.md D-02]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | pdf_processor.extract_pdf_content() | Already handles PyMuPDF, tables, bounding boxes |
| Text chunking | Custom text splitter | pdf_processor.chunk_into_parents() + chunk_parents_into_children() | Already handles parent-child strategy, token counting |
| Embedding generation | Custom embedding API call | BGEEmbeddingClient.generate_embeddings() | Already handles batching, retry, rate limiting |
| Vector storage/search | Custom Qdrant operations | QdrantVectorStore (collection="policy_documents") | Already handles CRUD, filtering, batch upsert |
| LLM client creation | Custom DeepSeek integration | create_llm("deepseek") | Already handles config, API key, retry |
| Redis caching | Custom cache logic | CacheManager + cacheable() | Already handles TTL, serialization, graceful degradation |
| LLM response parsing | Custom JSON extraction | NarrativeService._parse_llm_response() pattern | Already handles JSON in code blocks, mixed text |

**Key insight:** This phase is primarily a composition of existing components, not new infrastructure. The new code is: (1) AKShare method for business description, (2) LLM prompts for match verification and metadata extraction, (3) pure calculation functions for resonance scoring, (4) API route wiring.

## Common Pitfalls

### Pitfall 1: Wrong AKShare Function for Business Descriptions
**What goes wrong:** D-01 says `stock_individual_info_em()`, but it returns only basic info (price, shares, industry), not business descriptions.
**Why it happens:** Documentation/prd may not have been tested against actual AKShare API.
**How to avoid:** Use `stock_profile_cninfo(symbol='600519')` which returns `主营业务` and `经营范围` fields. This function accepts 6-digit stock codes.
**Warning signs:** If business_description is empty or None after AKShare call, check that the correct function is being used.

### Pitfall 2: Score Calculation with Zero Relevant Matches
**What goes wrong:** Division by zero or NaN if LLM marks all matches as `relevant=false`.
**Why it happens:** D-04 says "only verified-relevant matches contribute to the score." If all 5 matches are irrelevant, there are 0 data points.
**How to avoid:** Explicitly handle the zero-match case: `if no relevant matches found, score = 0` (per D-04). The pure function should return 0.0, not NaN.

### Pitfall 3: Qdrant Collection Not Created Before First Search
**What goes wrong:** `search()` on `policy_documents` collection fails if collection does not exist.
**Why it happens:** The annual_reports collection is created during app startup, but policy_documents needs its own initialization.
**How to avoid:** Call `ensure_collection_exists()` with custom payload indexes (policy_type, issuing_body, effective_date) before first upsert or search. Follow the existing pattern in QdrantVectorStore.ensure_collection_exists().

### Pitfall 4: LLM Metadata Extraction Timing
**What goes wrong:** Extracting metadata AFTER chunking means the LLM call runs on the full document, which may be too large for a single prompt.
**Why it happens:** Policy documents can be 20+ pages.
**How to avoid:** Extract metadata from the first 1-2 pages or first ~2000 tokens of extracted content, not the entire document. This is sufficient for title, type, issuing_body, and effective_date.

### Pitfall 5: DCF Adjustment Exceeding Terminal Growth Bounds
**What goes wrong:** Adding +1.5% to an already high terminal_growth could exceed ValuationConfig.MAX_TERMINAL_GROWTH = 10%.
**Why it happens:** D-08 says hard cap at +1.5%, but ValuationConfig.MAX_TERMINAL_GROWTH = 0.10 is the absolute bound.
**How to avoid:** Clamp the adjusted terminal growth: `min(original + adjustment, MAX_TERMINAL_GROWTH)`. Document this in the pure function.

### Pitfall 6: Empty Qdrant Policy Collection
**What goes wrong:** Resonance analysis requested before any policy documents uploaded.
**Why it happens:** User might call the resonance endpoint before uploading any policies.
**How to avoid:** Return score=0, tier=Neutral, adjustment=0% with a message indicating no policy documents available. Do not raise an error.

## Code Examples

### AKShare Business Description Fetch
```python
# Source: verified with AKShare 1.18.46 runtime test
async def get_stock_business_description(self, symbol: str) -> dict[str, str]:
    """Fetch stock business description from CNInfo via AKShare.

    Args:
        symbol: 6-digit stock code (e.g., '600519')

    Returns:
        Dict with 'main_business' and 'business_scope' keys.
    """

    def _fetch() -> dict[str, str]:
        import akshare as ak

        df = ak.stock_profile_cninfo(symbol=symbol)
        if df is None or df.empty:
            return {"main_business": "", "business_scope": ""}
        row = df.iloc[0]
        return {
            "main_business": str(row.get("主营业务", "")),
            "business_scope": str(row.get("经营范围", "")),
        }

    return await self._run_sync(_fetch)
```

### Resonance Score Calculation (Pure Function)
```python
def calculate_resonance_score(
    verified_matches: list[dict[str, Any]],
) -> float:
    """Calculate policy resonance score per D-04.

    Formula: 60% * (avg_cosine_similarity * 100) + 40% * (avg_llm_confidence * 100)
    Only relevant=True matches contribute.

    Args:
        verified_matches: List of dicts with 'score', 'relevant', 'confidence' keys.

    Returns:
        Resonance score 0-100. Returns 0.0 if no relevant matches.

    Examples:
        >>> calculate_resonance_score([
        ...     {"score": 0.85, "relevant": True, "confidence": 0.9, "reason": "..."},
        ...     {"score": 0.75, "relevant": True, "confidence": 0.8, "reason": "..."},
        ... ])
        81.0
        >>> calculate_resonance_score([
        ...     {"score": 0.85, "relevant": False, "confidence": 0.1, "reason": "..."},
        ... ])
        0.0
    """
    relevant = [m for m in verified_matches if m.get("relevant") is True]
    if not relevant:
        return 0.0

    avg_cosine = sum(m["score"] for m in relevant) / len(relevant)
    avg_confidence = sum(m["confidence"] for m in relevant) / len(relevant)

    return 0.60 * (avg_cosine * 100) + 0.40 * (avg_confidence * 100)
```

### DCF Terminal Growth Adjustment (Pure Function)
```python
def calculate_dcf_adjustment(
    resonance_score: float,
    original_terminal_growth: float,
    max_terminal_growth: float = 0.10,
) -> dict[str, Any]:
    """Calculate DCF terminal growth adjustment per D-07 and D-08.

    Args:
        resonance_score: 0-100 score from calculate_resonance_score().
        original_terminal_growth: Current terminal growth rate (e.g., 0.025).
        max_terminal_growth: Absolute cap from ValuationConfig (default 0.10).

    Returns:
        Dict with tier, adjustment_pct, adjusted_terminal_growth, original_terminal_growth.
    """
    if resonance_score >= 80.0:
        tier = "STRONGLY_SUPPORTIVE"
        adjustment = 0.015  # +1.5%
    elif resonance_score >= 40.0:
        tier = "SUPPORTIVE"
        adjustment = 0.01   # +1.0%
    else:
        tier = "NEUTRAL"
        adjustment = 0.0

    # D-08: Hard cap at +1.5%, subject to ValuationConfig absolute cap
    adjusted = min(original_terminal_growth + adjustment, max_terminal_growth)

    return {
        "tier": tier,
        "adjustment_pct": adjustment,
        "adjusted_terminal_growth": round(adjusted, 6),
        "original_terminal_growth": original_terminal_growth,
    }
```

### Policy Documents Qdrant Collection Setup
```python
# Source: extends QdrantVectorStore.ensure_collection_exists() pattern
def ensure_policy_collection_exists(self) -> None:
    """Create policy_documents collection with policy-specific payload indexes."""
    try:
        self.client.get_collection("policy_documents")
        return
    except Exception:
        pass

    self.client.create_collection(
        collection_name="policy_documents",
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    # Policy-specific payload indexes (D-12)
    for field_name, schema_type in [
        ("document_id", PayloadSchemaType.KEYWORD),
        ("policy_type", PayloadSchemaType.KEYWORD),
        ("issuing_body", PayloadSchemaType.KEYWORD),
        ("effective_date", PayloadSchemaType.KEYWORD),
        ("chunk_type", PayloadSchemaType.KEYWORD),
    ]:
        self.client.create_payload_index(
            collection_name="policy_documents",
            field_name=field_name,
            field_schema=schema_type,
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Policy keyword matching | Vector semantic matching + LLM verification | Phase 11 design | Reduces false positives, handles paraphrased policy language |
| Manual policy classification | LLM auto-extraction of metadata | Phase 11 design | Eliminates manual tagging, scales to any number of documents |
| Static terminal growth | Dynamic adjustment based on policy alignment | Phase 11 design | DCF model reflects current policy environment |

**No deprecated dependencies:** All existing project dependencies remain current and supported.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `stock_profile_cninfo()` is stable and available in AKShare 1.18.46 | Standard Stack | Would need alternative data source for business descriptions |
| A2 | BGE-M3 embedding quality is sufficient for policy-stock semantic matching across Chinese policy documents and business descriptions | Architecture | Low quality matches would reduce resonance score accuracy |
| A3 | DeepSeek can reliably output structured JSON for match verification `{relevant, confidence, reason}` and metadata extraction | Architecture | Would need fallback to simpler matching or different LLM |
| A4 | `stock_profile_cninfo()` accepts 6-digit codes for all CSI 300 stocks (verified with 600519, 000002) | Code Examples | Some stocks might need different symbol format |
| A5 | Policy PDFs are typically under 100MB and can be processed in memory | Architecture | Very large PDFs might need streaming processing |

## Open Questions

1. **Business description field selection: Should we use `主营业务` alone or concatenate with `经营范围`?**
   - What we know: `主营业务` is concise (e.g., "贵州茅台酒系列产品的产品研制、酿造生产、包装和销售。") while `经营范围` is more detailed and legalistic
   - What's unclear: Which field produces better semantic matches against policy text
   - Recommendation: Use `主营业务` as primary. If shorter than 50 characters, concatenate with `经营范围`. This balances semantic richness with noise.

2. **Should the `policy_documents` Qdrant collection use parent-child chunking like `annual_reports`?**
   - What we know: Annual reports use parent-child strategy (2000/500 tokens). Policy documents may be shorter.
   - What's unclear: Average policy document length
   - Recommendation: Use the same parent-child strategy for consistency. Policy documents can be long (multi-year plans, detailed regulations). Reuse existing chunking parameters from RAGConfig.

3. **How to handle the `business_description` column in StockDB when it is not yet populated?**
   - What we know: Existing stocks in the DB will not have this column populated initially
   - What's unclear: Whether to backfill all CSI 300 stocks or lazy-load on first request
   - Recommendation: Lazy-load with Redis cache. First request triggers AKShare fetch + DB update + Redis cache. Subsequent requests use cache.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Qdrant (Docker) | Policy vector storage | Needs verification | -- | Local Qdrant instance must be running on port 6333 |
| Redis | Business description caching | Needs verification | -- | CacheManager handles missing Redis gracefully |
| PostgreSQL | Policy document metadata | Needs verification | 15.x | -- |
| AKShare API | Business descriptions | Yes | 1.18.46 | -- |
| OpenRouter API | BGE-M3 embeddings | Needs API key | -- | No fallback for embedding generation |
| DeepSeek API | LLM verification | Needs API key | -- | Graceful degradation: skip LLM, use cosine-only score |

**Missing dependencies with no fallback:**
- Qdrant must be running for policy document storage and search
- OpenRouter API key (OPENROUTER_API_KEY) needed for BGE-M3 embeddings

**Missing dependencies with fallback:**
- Redis: If unavailable, business descriptions fetched from AKShare every time (slower but functional)
- DeepSeek: If unavailable, skip LLM verification, use cosine similarity only (less accurate but functional)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | stockvaluefinder/pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_policy_service.py -x` |
| Full suite command | `cd stockvaluefinder && uv run pytest --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| POL-01 | Policy PDF upload, chunking, Qdrant storage, metadata extraction | Unit + Integration | `uv run pytest tests/unit/test_services/test_policy_service.py -x` | Wave 0 |
| POL-02 | Vector similarity matching with LLM verification | Unit | `uv run pytest tests/unit/test_services/test_policy_service.py::test_verify_match_relevance -x` | Wave 0 |
| POL-03 | Resonance score calculation (0-100) | Unit | `uv run pytest tests/unit/test_services/test_policy_service.py::test_calculate_resonance_score -x` | Wave 0 |
| POL-04 | DCF terminal growth auto-adjustment | Unit | `uv run pytest tests/unit/test_services/test_policy_service.py::test_calculate_dcf_adjustment -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_services/test_policy_service.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_services/test_policy_service.py` -- covers POL-01 through POL-04 pure function tests
- [ ] `tests/unit/test_external/test_akshare_business_desc.py` -- covers AKShare stock_profile_cninfo mock
- [ ] Existing `tests/unit/test_rag/` covers pdf_processor and vector_store reuse

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in current milestone |
| V3 Session Management | no | No sessions in current milestone |
| V4 Access Control | no | No access control in current milestone |
| V5 Input Validation | yes | Pydantic Field validation on ticker pattern, file type/size validation |
| V6 Cryptography | no | No cryptographic operations |

### Known Threat Patterns for Policy Upload

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious PDF upload | Tampering | File type validation, size limit (100MB), PyMuPDF sandbox |
| Path traversal in filename | Tampering | Filename sanitization (reuse `_sanitize_filename` from documents_routes.py) |
| Prompt injection in policy content | Spoofing | LLM output is never executed as code; parse as JSON with fallback |
| Excessive Qdrant storage | Denial of Service | Rate limit uploads, max file size per upload |

## Existing Code Reuse Analysis

### Full Reuse (No Changes Needed)
| Component | File | What It Does for Phase 11 |
|-----------|------|--------------------------|
| BGEEmbeddingClient | rag/embeddings.py | Generates 1024-dim vectors for policy chunks and stock descriptions |
| extract_pdf_content() | rag/pdf_processor.py | Extracts text from policy PDFs |
| chunk_into_parents() | rag/pdf_processor.py | Splits policy content into parent chunks |
| chunk_parents_into_children() | rag/pdf_processor.py | Splits parent chunks into child chunks |
| CacheManager | utils/cache.py | Caches business descriptions in Redis |
| create_llm("deepseek") | llm_factory.py | Creates DeepSeek LLM client for verification and metadata extraction |
| ApiResponse[T] | models/api.py | Standard response envelope for policy endpoints |
| _sanitize_filename() | api/documents_routes.py | Filename sanitization for policy PDF uploads |
| NarrativeService._parse_llm_response() | services/narrative_service.py | JSON extraction from LLM responses |

### Extension Needed (Modify Existing)
| Component | File | What Changes |
|-----------|------|-------------|
| AKShareClient | external/akshare_client.py | Add `get_stock_business_description()` method using `stock_profile_cninfo()` |
| ExternalDataService | external/data_service.py | Add `get_business_description(ticker)` with Redis cache |
| StockDB | db/models/stock.py | Add `business_description` column (Text, nullable) |
| AppConfig | config.py | Add `PolicyResonanceConfig` frozen dataclass |
| main.py | main.py | Register `policy_router` |

### New Files Needed
| File | Purpose |
|------|---------|
| api/policy_routes.py | Upload endpoint + resonance analysis endpoint |
| services/policy_service.py | Pure functions: calculate_resonance_score, calculate_dcf_adjustment, verify_matches |
| models/policy.py | Pydantic models: PolicyUploadRequest, PolicyUploadResponse, ResonanceRequest, ResonanceResult, PolicyMatch, PolicyMetadata |
| db/models/policy.py | PolicyDocumentDB ORM model (stores upload metadata) |
| repositories/policy_repo.py | PolicyDocumentRepository for DB operations |
| alembic/versions/013_policy_tables.py | Migration: policy_documents table + stocks.business_description column |

## Sources

### Primary (HIGH confidence)
- AKShare `stock_profile_cninfo()` -- verified by runtime test on 2026-05-06 with symbols 600519 and 000002
- QdrantVectorStore code review -- verified cross-collection search works with same embedding model
- BGEEmbeddingClient code review -- verified generates same 1024-dim vectors regardless of input source
- pdf_processor.py code review -- verified handles generic PDF input, not annual-report-specific
- valuation_service.py code review -- verified `calculate_terminal_value()` uses `terminal_growth` parameter at line 112-126
- config.py code review -- verified `ValuationConfig.MAX_TERMINAL_GROWTH = 0.10` and frozen dataclass pattern

### Secondary (MEDIUM confidence)
- CONTEXT.md D-01 through D-12 -- design decisions from discuss-phase, authoritative for this phase
- ROADMAP.md Phase 11 goal and success criteria -- defines phase scope
- Existing codebase patterns (capex_routes.py, NarrativeService) -- establish conventions

### Tertiary (LOW confidence)
- LLM prompt design for policy-stock match verification -- needs iterative testing during implementation
- LLM prompt design for policy metadata extraction -- needs iterative testing during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already installed and verified
- Architecture: HIGH -- cross-collection search verified, existing RAG pipeline fully reusable
- Pitfalls: HIGH -- wrong AKShare function caught during research, not during implementation
- AKShare API: HIGH -- runtime tested with multiple symbols

**Research date:** 2026-05-06
**Valid until:** 2026-06-05 (AKShare APIs can change between versions)
