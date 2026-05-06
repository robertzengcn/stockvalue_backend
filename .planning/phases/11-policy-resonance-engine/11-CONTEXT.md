# Phase 11: Policy Resonance Engine - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can measure how well a stock aligns with government policy direction through document-based semantic matching. This phase delivers: policy PDF upload with metadata extraction, dedicated Qdrant collection (`policy_documents`), vector similarity matching of policy text against stock business descriptions, LLM-verified relevance classification, 0-100 resonance scoring with matched excerpts, and automatic DCF terminal growth rate adjustment based on resonance tier.

</domain>

<decisions>
## Implementation Decisions

### Stock-Business-to-Policy Matching
- **D-01:** Stock business descriptions sourced from AKShare `stock_individual_info_em()` (经营范围/主营业务 field). Add `business_description` column to `StockDB` model. Fetch + cache per stock with Redis TTL consistent with existing patterns.
- **D-02:** Top 5 policy document chunks matched per stock for broader coverage across multi-domain policies. Returns top 5 most relevant matched excerpts with scores.
- **D-03:** LLM (DeepSeek) classification used to verify matches and reduce false positives after vector similarity search. Vector similarity finds candidate matches, LLM confirms true relevance per ROADMAP POL-02.

### Resonance Scoring Formula
- **D-04:** Weighted formula for resonance score (0-100): `60% * (avg_cosine_similarity * 100) + 40% * (avg_llm_confidence * 100)`. Only verified-relevant matches (LLM `relevant=true`) contribute to the score. If no relevant matches found, score = 0.
- **D-05:** LLM returns structured verdict per match: `{relevant: bool, confidence: float 0-1, reason: string}`. Confidence feeds into score formula, relevant flag filters non-matches. Reason included in API response for audit trail.
- **D-06:** Resonance threshold of 40/100 to qualify as 'policy-aligned' for DCF adjustment purposes.

### DCF Auto-Adjustment Rules
- **D-07:** Tiered DCF terminal growth adjustment based on resonance score: Strongly Supportive (>=80, +1.5%), Supportive (40-79, +1.0%), Neutral (<40, 0%). No negative adjustment — restrictive policies are hard to detect reliably from text.
- **D-08:** Hard cap on terminal growth adjustment at +1.5%. Subject to existing `ValuationConfig.MAX_TERMINAL_GROWTH = 10%` absolute cap.
- **D-09:** Combined API response: resonance score, tier label, matched policy excerpts, DCF adjustment details (adjustment_pct, adjusted_terminal_growth, original_terminal_growth) returned in single endpoint call.

### Policy Document Metadata & Storage
- **D-10:** Enriched metadata per policy document: title, upload_date, policy_type (industry/fiscal/monetary/trade), issuing_body (国务院/证监会/发改委/etc), effective_date, industry_tags. LLM auto-extracts these from document content during upload processing.
- **D-11:** Match ALL uploaded policy documents against a stock when requesting resonance analysis. No pre-selection needed — upload once, applies to all stocks.
- **D-12:** Separate Qdrant collection named `policy_documents` with its own payload indexes (policy_type, issuing_body, effective_date). Different metadata schema from `annual_reports` collection per ROADMAP decision.

### Claude's Discretion
- Exact AKShare method name and field mapping for business descriptions (verify `stock_individual_info_em()` availability)
- Policy upload API endpoint path and request/response models
- New ORM model field names and Alembic migration details
- LLM prompt engineering for match verification and metadata extraction
- Internal function organization within policy_service.py
- Test file structure and test case selection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Alpha Engine PRD
- `doc/Alpha_Engine_V2.0/Alpha_Engine_V2.0.md` — Original PRD with policy resonance specification, DCF adjustment concept

### Existing RAG Pipeline (critical for this phase)
- `stockvaluefinder/stockvaluefinder/rag/vector_store.py` — `QdrantVectorStore` with collection creation, upsert, search, delete. Reuse for `policy_documents` collection.
- `stockvaluefinder/stockvaluefinder/rag/retriever.py` — `SemanticRetriever` with multi-query expansion pattern. Reference for match verification flow.
- `stockvaluefinder/stockvaluefinder/rag/embeddings.py` — `BGEEmbeddingClient` with BGE-M3 1024-dim vectors via OpenRouter. Reuse for policy embeddings.
- `stockvaluefinder/stockvaluefinder/rag/pdf_processor.py` — PDF processing with parent-child chunking. Reuse for policy PDF processing.
- `stockvaluefinder/stockvaluefinder/rag/document.py` — `DocumentChunk`, `ChunkMetadata` dataclasses. Extend for policy-specific metadata.

### Stock Data & Models
- `stockvaluefinder/stockvaluefinder/db/models/stock.py` — `StockDB` model. Add `business_description` column.
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — Add business description fetch method.
- `stockvaluefinder/stockvaluefinder/external/data_service.py` — Add `get_stock_business_description()` with caching.

### DCF Integration
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` — `calculate_terminal_value()` at line ~107 uses `terminal_growth`. DCF adjustment feeds into this parameter.
- `stockvaluefinder/stockvaluefinder/models/valuation.py` — `DCFParams` with `terminal_growth` field. Adjustment applies to this value.
- `stockvaluefinder/stockvaluefinder/config.py` — `ValuationConfig` with `MIN_TERMINAL_GROWTH=-0.05`, `MAX_TERMINAL_GROWTH=0.10`. Adjusted terminal growth must stay within these bounds.

### LLM Integration
- `stockvaluefinder/stockvaluefinder/llm_factory.py` — `create_llm()` factory for DeepSeek. Reuse for policy match verification and metadata extraction.
- `stockvaluefinder/stockvaluefinder/services/narrative_service.py` — LLM call patterns with graceful fallback.

### Project Context
- `.planning/PROJECT.md` — Current milestone goals, validated requirements, constraints
- `.planning/REQUIREMENTS.md` — POL-01 through POL-04 requirements
- `.planning/ROADMAP.md` — Phase 11 goal, success criteria, dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `QdrantVectorStore`: Full Qdrant CRUD with collection management. Instantiate with `collection="policy_documents"` and custom payload indexes.
- `BGEEmbeddingClient`: BGE-M3 embeddings via OpenRouter. Same 1024-dim vectors for cross-collection similarity search.
- `pdf_processor.py`: PDF text extraction with PyMuPDF, parent-child chunking. Reuse for policy PDFs.
- `SemanticRetriever`: Search + multi-query expansion pattern. Reference for policy-to-stock matching flow.
- `create_llm("deepseek")`: LLM client factory for match verification and metadata extraction prompts.
- `CacheManager` in utils/cache.py: Redis caching with TTL and decorator pattern for business descriptions.

### Established Patterns
- Pure function services: All calculations as stateless pure functions in `services/` directory
- Frozen config dataclasses: Add `PolicyResonanceConfig` with `frozen=True`
- API envelope: `ApiResponse[T]` with success/data/error fields
- Route pattern: `POST /api/v1/analyze/{domain}` with dependency injection
- Separate Qdrant collections: Different schemas warrant separate collections (annual_reports vs policy_documents)
- LLM graceful fallback: Return None/default on LLM failures (narrative_service pattern)

### Integration Points
- StockDB model: Add `business_description` column via Alembic migration
- AKShare client: Add method for stock business description fetch
- Qdrant: New `policy_documents` collection alongside existing `annual_reports`
- DCF valuation: Terminal growth adjustment feeds into `DCFParams.terminal_growth` parameter
- Existing upload pattern: `POST /api/v1/documents/upload` for annual reports — similar flow for policy uploads

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. All decisions are captured in the Implementation Decisions section above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-Policy Resonance Engine*
*Context gathered: 2026-05-06*
