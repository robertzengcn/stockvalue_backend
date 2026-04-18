# Phase 4: RAG Pipeline - Research

**Researched:** 2026-04-18
**Domain:** RAG pipeline (PDF processing, embeddings, vector search, semantic retrieval)
**Confidence:** HIGH

## Summary

Phase 4 builds a complete RAG pipeline enabling PDF annual report upload, intelligent chunking with table preservation, bge-m3 embedding generation, Qdrant vector storage, and semantic retrieval with parent-child document pairing. The existing codebase has stub RAG modules (`rag/vector_store.py`, `rag/retriever.py`, `rag/embeddings.py`, `rag/pdf_processor.py`) that are all TODO placeholders. The project already has `qdrant-client>=1.17.0` and `httpx>=0.27.0` in dependencies but lacks PDF processing and embedding libraries.

**Primary recommendation:** Use PyMuPDF (pymupdf) for PDF parsing with its built-in `find_tables()` method, OpenRouter as the bge-m3 embedding API provider (OpenAI-compatible endpoint at $0.01/M tokens, 1024 dimensions), and implement a custom parent-child chunking strategy that preserves financial tables as atomic units. Store child chunks in Qdrant with parent_id references, retrieve parent context on search hits.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Upload format -- Multipart form-data with file upload (`POST /api/v1/documents/upload` with `file: UploadFile`)
- **D-02:** Table handling -- Preserve financial tables intact even if they exceed 500-token chunk size
- **D-03:** Extraction depth -- Full structure with page references (headers, sections, tables, page numbers)
- **D-04:** bge-m3 deployment -- API version (not local model), reduces infrastructure complexity
- **D-05:** Qdrant setup -- Self-hosted Docker
- **D-06:** Metadata schema -- Index 6 fields: ticker, year, report type, company name, filing date, document section
- **D-07:** Response format -- Child + parent pairing (500-token child with 2000-token parent context)
- **D-08:** Result limiting -- Hybrid: up to N results exceeding relevance score threshold (>0.7)
- **D-09:** Query expansion -- Multi-query expansion enabled (3-5 variations via LLM, aggregate and deduplicate)
- **D-10:** Architecture -- Standalone document endpoints + optional `document_ids` parameter in analysis endpoints
- **D-11:** Document linking -- Ticker required at upload time
- **D-12:** Auto-trigger -- No, manual trigger only

### Claude's Discretion
- Specific API endpoint paths and request/response schemas
- bge-m3 API provider choice (Together AI, Anyscale, or other)
- Qdrant collection configuration (vector dimensions, distance metric)
- Chunking algorithm details (token counting method, table detection heuristics)
- Multi-query expansion prompt design and result deduplication strategy
- Relevance score threshold and result limit default values

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-03 | RAG pipeline: PDF upload endpoint that accepts annual report PDFs | FastAPI `UploadFile` pattern established in codebase; multipart form-data endpoint follows existing route patterns |
| DATA-04 | RAG pipeline: PDF processing with chunking (500-token child, 2000-token parent documents) | PyMuPDF `find_tables()` for table detection; tiktoken for token counting; custom parent-child chunking strategy documented |
| DATA-05 | RAG pipeline: bge-m3 embedding generation for Chinese financial text | OpenRouter provides bge-m3 API (1024-dim, OpenAI-compatible); httpx already in deps for HTTP calls |
| DATA-06 | RAG pipeline: Qdrant vector store integration with metadata filtering (year, industry, ticker) | qdrant-client 1.17.0 already in deps; self-hosted Docker; payload indexes for metadata filtering |
| DATA-07 | RAG pipeline: Semantic retrieval endpoint returning parent-document context with source page references | Parent-child retrieval pattern; Qdrant search with payload filters; page references stored in chunk metadata |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pymupdf | 1.27.2 | PDF text extraction, table detection, page structure | Built-in `find_tables()` with markdown export, OCR support, CJK text handling. Fastest Python PDF library. [VERIFIED: PyPI registry] |
| qdrant-client | 1.17.1 | Vector database client | Already in project deps. Supports sync/async, payload filtering, batch upsert. [VERIFIED: PyPI registry, installed 1.17.0] |
| tiktoken | 0.12.0 | Token counting for chunking | Already installed. cl100k_base encoding for accurate token counting. [VERIFIED: PyPI registry, installed] |
| httpx | 0.28.1 | HTTP client for embedding API calls | Already in project deps. Used throughout codebase for async HTTP. [VERIFIED: installed] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| alembic | 1.18+ | Database migration for new `documents` table | Already in deps. New ORM model needs migration. [VERIFIED: installed] |
| sqlalchemy | 2.0+ | ORM for document metadata storage | Already in deps. Documents table follows existing model patterns. [VERIFIED: installed] |
| pydantic | 2.12+ | Request/response models for document endpoints | Already in deps. Follow existing model patterns. [VERIFIED: installed] |
| fastapi | 0.133+ | Upload endpoint with `UploadFile` | Already in deps. Standard multipart handling. [VERIFIED: installed] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pymupdf | pdfplumber 0.11.9 | pdfplumber has better table extraction for complex layouts but slower and no markdown export. PyMuPDF's `find_tables()` is sufficient for structured annual reports [ASSUMED] |
| OpenRouter (bge-m3) | Together AI (bge-large-en-v1.5) | Together AI does NOT offer bge-m3, only bge-large-en-v1.5 (English-only, 1024-dim). BGE-M3 is required for Chinese text support. [VERIFIED: Together AI docs] |
| OpenRouter (bge-m3) | Self-hosted bge-m3 | Local deployment needs GPU, increases infra complexity. API approach matches D-04 decision. OpenRouter at $0.01/M tokens is cost-effective for MVP. [VERIFIED: OpenRouter pricing] |
| Single Qdrant collection | Per-stock collections | Single collection with metadata filtering is simpler to manage, avoids collection proliferation with 300 stocks. Recommended approach. [ASSUMED] |

**Installation:**
```bash
uv add pymupdf
# qdrant-client, tiktoken, httpx already installed
```

**Version verification:**
```
pymupdf: 1.27.2.2 (latest on PyPI, 2026-04-18)
qdrant-client: 1.17.1 (latest on PyPI, installed 1.17.0)
tiktoken: 0.12.0 (latest on PyPI, installed)
httpx: 0.28.1 (installed)
```

## Architecture Patterns

### Recommended Project Structure
```
stockvaluefinder/stockvaluefinder/
├── rag/
│   ├── __init__.py
│   ├── pdf_processor.py      # PDF parsing, chunking, table extraction
│   ├── embeddings.py          # bge-m3 embedding client (OpenRouter API)
│   ├── vector_store.py        # Qdrant client wrapper (CRUD, search)
│   └── retriever.py           # Semantic search + multi-query expansion
├── api/
│   ├── documents_routes.py    # Upload & search endpoints
│   ├── dependencies.py        # Add get_qdrant_client() dependency
│   └── stock_helpers.py       # Shared helpers (existing)
├── models/
│   └── document.py            # Pydantic models for documents
├── db/models/
│   └── document.py            # SQLAlchemy ORM model for documents table
├── repositories/
│   └── document_repo.py       # Document repository
├── services/
│   └── document_service.py    # Orchestration: upload -> parse -> embed -> store
└── config.py                  # Add RAGConfig dataclass
```

### Pattern 1: Parent-Child Document Chunking
**What:** Split PDF into 2000-token parent chunks, then further split parents into 500-token child chunks. Tables are preserved as atomic units even if they exceed 500 tokens.
**When to use:** This is the core chunking strategy for all uploaded documents.
**Example:**
```python
# Source: Parent-Child Chunking pattern (LangChain, multiple sources)
from dataclasses import dataclass

@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to every chunk stored in Qdrant."""
    document_id: str
    parent_id: str | None       # None for parent chunks
    page_number: int
    section: str
    ticker: str
    year: int
    report_type: str
    company_name: str
    filing_date: str
    chunk_type: str             # "parent" | "child" | "table"
    token_count: int

@dataclass(frozen=True)
class DocumentChunk:
    """A single chunk extracted from a PDF document."""
    chunk_id: str
    content: str
    metadata: ChunkMetadata
```

### Pattern 2: Qdrant Single Collection with Payload Filtering
**What:** One collection `annual_reports` with all documents. Metadata fields (ticker, year, report_type, etc.) stored as payload and indexed for filtering.
**When to use:** All vector storage and retrieval.
**Example:**
```python
# Source: Qdrant Python client documentation
# [CITED: https://github.com/qdrant/qdrant-client]
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)

client = QdrantClient(url="http://localhost:6333")

# Create collection with 1024-dim vectors (bge-m3 output)
client.create_collection(
    collection_name="annual_reports",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
)

# Create payload indexes for filtered search
client.create_payload_index(
    collection_name="annual_reports",
    field_name="ticker",
    field_schema=PayloadSchemaType.KEYWORD,
)
client.create_payload_index(
    collection_name="annual_reports",
    field_name="year",
    field_schema=PayloadSchemaType.INTEGER,
)

# Upsert child chunks with parent reference
client.upsert(
    collection_name="annual_reports",
    points=[
        PointStruct(
            id="child_chunk_uuid",
            vector=[0.1, 0.2, ...],  # 1024-dim from bge-m3
            payload={
                "document_id": "doc_uuid",
                "parent_id": "parent_chunk_uuid",
                "page_number": 12,
                "section": "financial_statements",
                "ticker": "600519.SH",
                "year": 2023,
                "report_type": "annual",
                "company_name": "Kweichow Moutai",
                "filing_date": "2024-03-28",
                "chunk_type": "child",
                "token_count": 480,
            },
        ),
    ],
)

# Search with metadata filter
results = client.search(
    collection_name="annual_reports",
    query_vector=query_embedding,  # 1024-dim
    query_filter=Filter(
        must=[
            FieldCondition(key="ticker", match=MatchValue(value="600519.SH")),
            FieldCondition(key="year", match=MatchValue(value=2023)),
            FieldCondition(key="chunk_type", match=MatchValue(value="child")),
        ]
    ),
    limit=10,
    score_threshold=0.7,
)
```

### Pattern 3: OpenAI-Compatible Embedding API via OpenRouter
**What:** Call bge-m3 through OpenRouter's OpenAI-compatible endpoint using httpx.
**When to use:** All embedding generation for chunks and queries.
**Example:**
```python
# Source: OpenRouter API documentation
# [CITED: https://openrouter.ai/baai/bge-m3]
import httpx
import os

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
EMBEDDING_API_URL = "https://openrouter.ai/api/v1/embeddings"

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate bge-m3 embeddings via OpenRouter API.

    Args:
        texts: List of text strings to embed (batch supported)

    Returns:
        List of 1024-dimensional float vectors
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            EMBEDDING_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "baai/bge-m3",
                "input": texts,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]
```

### Pattern 4: PDF Processing with PyMuPDF
**What:** Extract text, tables, and page structure from PDF using PyMuPDF with page tracking.
**When to use:** All PDF upload processing.
**Example:**
```python
# Source: PyMuPDF documentation
# [CITED: https://pymupdf.readthedocs.io/en/latest/page.html]
import pymupdf

def extract_pdf_content(pdf_bytes: bytes) -> list[dict]:
    """Extract structured content from PDF with page references.

    Returns list of content blocks with type, text, page number, and bbox.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    blocks = []

    for page_num in range(doc.page_count):
        page = doc[page_num]

        # Extract text blocks with structure
        text_dict = page.get_text("dict", sort=True)
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                text = "".join(
                    span["text"]
                    for line in block["lines"]
                    for span in line["spans"]
                ).strip()
                if text:
                    blocks.append({
                        "type": "text",
                        "content": text,
                        "page": page_num + 1,
                        "bbox": tuple(block["bbox"]),
                    })

        # Extract tables (preserved as complete units)
        tables = page.find_tables()
        for table in tables:
            table_md = table.to_markdown()
            if table_md.strip():
                blocks.append({
                    "type": "table",
                    "content": table_md,
                    "page": page_num + 1,
                    "bbox": tuple(table.bbox),
                })

    doc.close()
    return blocks
```

### Anti-Patterns to Avoid
- **Naive fixed-size chunking:** Splitting on token boundaries without respecting table/section boundaries destroys financial data integrity. Use structure-aware chunking.
- **Embedding the parent chunk for search:** Parent chunks are too broad for precise semantic matching. Only embed child chunks; retrieve parent by reference.
- **Storing parent content in Qdrant:** Qdrant payloads have practical size limits. Store parent content in PostgreSQL, store only child content + parent_id reference in Qdrant. Fetch parent from DB during retrieval.
- **Synchronous embedding calls in async FastAPI:** The upload endpoint is async; embedding calls must be async too. Use httpx.AsyncClient, not requests.
- **One Qdrant collection per stock:** With 300 CSI stocks, this creates collection management overhead. Use a single collection with payload filtering.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser with PyPDF2 | PyMuPDF (pymupdf) | Handles CJK text, tables, page structure, OCR. Battle-tested on complex PDFs. |
| Table detection from PDFs | Regex or layout-based table finder | PyMuPDF `find_tables()` | Built-in table detection with strategies (lines/text), markdown export, bbox tracking. |
| Token counting for chunking | Character-based or word-based approximation | tiktoken with cl100k_base encoding | Accurate token counting aligned with embedding model expectations. |
| Vector similarity search | Custom cosine similarity in numpy | Qdrant with COSINE distance | Optimized HNSW index, payload filtering, persistence, batch operations. |
| Embedding generation | Local model inference | OpenRouter bge-m3 API | No GPU needed, managed service, $0.01/M tokens. |
| Multi-query expansion | Custom query generation | LLM-based expansion via existing NarrativeService | Reuse existing LLM provider infrastructure, generate 3-5 query variations. |

**Key insight:** The RAG pipeline has many moving parts (PDF parsing, chunking, embedding, vector storage, retrieval, query expansion). Each component has mature library support. Building custom solutions for any of these would introduce bugs and maintenance burden without adding value.

## Common Pitfalls

### Pitfall 1: Chinese Text Tokenization Mismatch
**What goes wrong:** Using wrong tiktoken encoding or tokenizer that does not match bge-m3's expectations, leading to chunks that are too long or too short for the embedding model.
**Why it happens:** bge-m3 uses XLM-RoBERTa tokenizer (not GPT-style), so tiktoken's cl100k_base is an approximation. Chinese characters may count as 1-2 tokens depending on the encoding.
**How to avoid:** Use tiktoken as a reasonable approximation for chunking boundaries. BGE-M3 supports up to 8192 tokens, so 500-token chunks are well within limits. Add a safety margin (target 450 tokens instead of 500).
**Warning signs:** Embedding API returns errors about input length, or search quality degrades due to poorly sized chunks.

### Pitfall 2: Table Splitting Across Chunks
**What goes wrong:** A financial table spanning 800 tokens gets split mid-row, destroying the data structure.
**Why it happens:** Fixed-size chunking does not respect table boundaries.
**How to avoid:** Detect tables first via PyMuPDF's `find_tables()`, mark them as atomic chunks, and only split text content around tables. Tables that exceed 500 tokens become oversized child chunks (acceptable per D-02).
**Warning signs:** Search results return partial table rows; financial data appears garbled.

### Pitfall 3: Qdrant Not Running at Startup
**What goes wrong:** Application starts but Qdrant Docker container is not running, causing embedding/storage failures.
**Why it happens:** Qdrant is an external Docker service; no automatic dependency check.
**How to avoid:** Add a health check during FastAPI lifespan (similar to Redis cache pattern). Gracefully degrade if Qdrant is unavailable -- accept uploads, queue for later processing.
**Warning signs:** Upload endpoint returns 500 errors; embedding calls succeed but Qdrant upsert fails.

### Pitfall 4: Batch Embedding Rate Limits
**What goes wrong:** Uploading a 200-page annual report generates 100+ chunks; embedding API rejects large batches.
**Why it happens:** API providers have rate limits and batch size limits.
**How to avoid:** Batch chunks in groups of 20-50 for embedding calls. Add retry logic with exponential backoff. Process upload asynchronously (background task).
**Warning signs:** Partial uploads where some chunks have embeddings and others do not.

### Pitfall 5: Parent-Child Join Performance
**What goes wrong:** Retrieval fetches 10 child chunks, then makes 10 separate DB queries to fetch parent content -- slow and inefficient.
**Why it happens:** Not batching the parent fetch after search.
**How to avoid:** After Qdrant search returns child results, collect unique parent_ids and batch-fetch all parent content from PostgreSQL in a single query.
**Warning signs:** Search endpoint takes >2 seconds; N+1 query pattern in logs.

### Pitfall 6: PDF Encoding Issues with Chinese Text
**What goes wrong:** Chinese characters from annual reports come through as garbled text or mojibake.
**Why it happens:** Some Chinese PDFs use non-standard font encodings or embedded fonts with custom CMaps.
**How to avoid:** PyMuPDF handles most CJK text well, but test with real annual report PDFs early. For problematic PDFs, PyMuPDF's OCR support (`get_textpage_ocr()`) can be a fallback.
**Warning signs:** Extracted text contains `\ufffd` replacement characters; search quality is poor for Chinese queries.

## Code Examples

### Document ORM Model (follows existing pattern)
```python
# stockvaluefinder/db/models/document.py
"""SQLAlchemy ORM model for Document entity."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class DocumentDB(Base):
    """SQLAlchemy ORM model for uploaded documents."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique document identifier",
    )
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Linked stock ticker (FK to stocks)",
    )
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original file name",
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Storage path for the PDF file",
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of pages in the PDF",
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Processing status: pending, processing, completed, failed",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="Document metadata (year, report_type, company_name, filing_date)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
```

### Upload Endpoint Pattern (follows existing route pattern)
```python
# stockvaluefinder/api/documents_routes.py
"""Document upload and search API endpoints."""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.document import DocumentUploadResponse, DocumentSearchRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/upload", response_model=ApiResponse[DocumentUploadResponse])
async def upload_document(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    year: int = Form(...),
    report_type: str = Form("annual"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentUploadResponse]:
    """Upload and process a PDF annual report."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ApiResponse(success=False, error="Only PDF files are accepted")

    # Validate ticker format
    import re
    if not re.match(r"^\d{6}\.(SH|SZ|HK)$", ticker):
        return ApiResponse(success=False, error="Invalid ticker format")

    try:
        # Read file content
        content = await file.read()

        # Process asynchronously (parse -> chunk -> embed -> store)
        # ... document service orchestration ...

        return ApiResponse(success=True, data=DocumentUploadResponse(
            document_id="...",
            status="completed",
            chunk_count=42,
            page_count=200,
        ))
    except Exception as e:
        logger.exception(f"Failed to process upload: {e}")
        return ApiResponse(success=False, error="Failed to process document")


@router.post("/search", response_model=ApiResponse[list])
async def search_documents(
    request: DocumentSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list]:
    """Semantic search across indexed documents."""
    try:
        # Generate query embedding
        # Multi-query expansion (optional)
        # Qdrant search with metadata filters
        # Fetch parent context for each child match
        # Return results with page references
        ...
    except Exception as e:
        logger.exception(f"Search failed: {e}")
        return ApiResponse(success=False, error="Search failed")
```

### RAGConfig (follows existing config pattern)
```python
# Add to stockvaluefinder/config.py
@dataclass(frozen=True)
class RAGConfig:
    """Configuration for RAG pipeline."""

    # Qdrant connection
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "annual_reports"
    QDRANT_API_KEY: str | None = None

    # Embedding
    EMBEDDING_API_URL: str = "https://openrouter.ai/api/v1/embeddings"
    EMBEDDING_API_KEY_ENV: str = "OPENROUTER_API_KEY"
    EMBEDDING_MODEL: str = "baai/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32

    # Chunking
    CHILD_CHUNK_TOKENS: int = 500
    PARENT_CHUNK_TOKENS: int = 2000
    CHUNK_OVERLAP_TOKENS: int = 50

    # Search
    SEARCH_SCORE_THRESHOLD: float = 0.7
    SEARCH_RESULT_LIMIT: int = 10
    MULTI_QUERY_COUNT: int = 3

    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed-size chunking | Parent-child document retrieval | 2023-2024 | Better search precision with context preservation |
| pdfplumber for tables | PyMuPDF `find_tables()` (v1.23+) | PyMuPDF 1.23.0 | Built-in table detection, markdown export, no extra deps |
| Local embedding models | API-hosted bge-m3 | 2024-2025 | No GPU needed, pay-per-use, simpler deployment |
| Per-collection vector stores | Single collection with metadata filtering | Qdrant matured 2023 | Simpler management, better for multi-tenant access |
| Single-query retrieval | Multi-query expansion | 2023-2024 | Better recall for financial document search |

**Deprecated/outdated:**
- PyPDF2/PyPDF3: Superseded by PyMuPDF for feature completeness and performance
- FAISS in-memory index: Not suitable for production (no persistence, no metadata filtering)
- Sentence-transformers local inference: For MVP, API approach is simpler per D-04

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OpenRouter bge-m3 endpoint produces 1024-dim vectors compatible with Qdrant COSINE distance | Architecture Patterns | Collection config would be wrong; verify with test embedding call |
| A2 | tiktoken cl100k_base is a reasonable approximation for bge-m3's XLM-RoBERTa tokenizer boundaries | Common Pitfalls | Chunks may be slightly over/under target size; not critical for 500-token targets |
| A3 | Single Qdrant collection with metadata filtering scales well for MVP (300 stocks x ~10 reports = ~3000 documents) | Architecture Patterns | Would need to shard if scale increases; acceptable for MVP |
| A4 | PyMuPDF can handle Chinese annual report PDFs (most use standard fonts) | Common Pitfalls | Some PDFs with custom fonts may need OCR fallback |
| A5 | Financial tables in annual reports are detectable by PyMuPDF's line-based strategy | Architecture Patterns | Complex tables may need text-based strategy as fallback |

## Open Questions

1. **OpenRouter API Key Setup**
   - What we know: OpenRouter provides bge-m3 at $0.01/M tokens via OpenAI-compatible API
   - What's unclear: Whether the user has an OpenRouter account or prefers another provider
   - Recommendation: Start with OpenRouter; abstract embedding client behind interface to allow easy provider swap. Support env var `EMBEDDING_API_KEY` and `EMBEDDING_API_URL` for configuration.

2. **File Storage Location**
   - What we know: PDFs need to be stored somewhere after upload for potential reprocessing
   - What's unclear: Whether to use local filesystem, S3, or database storage
   - Recommendation: Local filesystem under `./uploads/` for MVP. Store path in database. Can migrate to S3 later.

3. **Background Processing vs. Synchronous**
   - What we know: PDF processing + embedding generation for a 200-page report could take 1-3 minutes
   - What's unclear: Whether to use background tasks or return immediately with a status polling endpoint
   - Recommendation: Use FastAPI `BackgroundTasks` for processing. Return `document_id` and `status="processing"` immediately. Add `GET /api/v1/documents/{document_id}/status` for polling.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | Y | 3.12+ | -- |
| PostgreSQL | Document metadata storage | Y | 15.x (port 5433) | -- |
| Docker | Qdrant container | Y | 29.1.3 | -- |
| Qdrant (running) | Vector storage | N | -- | Docker compose startup step |
| PyMuPDF | PDF parsing | N | -- | Must install (`uv add pymupdf`) |
| tiktoken | Token counting | Y | 0.12.0 | -- |
| qdrant-client | Vector DB client | Y | 1.17.0 | -- |
| httpx | Embedding API calls | Y | 0.28.1 | -- |
| OpenRouter API key | Embedding generation | N | -- | User must configure |

**Missing dependencies with no fallback:**
- PyMuPDF: Must install before implementation (`uv add pymupdf`)
- Qdrant Docker container: Must start before testing (`docker compose up -d qdrant`)
- OpenRouter API key: User must set `OPENROUTER_API_KEY` env var

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | `stockvaluefinder/pyproject.toml` (tool.pytest) |
| Quick run command | `uv run pytest tests/unit/test_rag/ -x -q` |
| Full suite command | `uv run pytest tests/ -x --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-03 | PDF upload endpoint accepts multipart form-data | unit | `uv run pytest tests/unit/test_api/test_documents_routes.py::test_upload_pdf -x` | Wave 0 |
| DATA-03 | Upload rejects non-PDF files | unit | `uv run pytest tests/unit/test_api/test_documents_routes.py::test_upload_rejects_non_pdf -x` | Wave 0 |
| DATA-04 | PDF is chunked into 500-token children, 2000-token parents | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_chunking_token_counts -x` | Wave 0 |
| DATA-04 | Tables preserved as atomic units | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_table_preservation -x` | Wave 0 |
| DATA-04 | Page references tracked per chunk | unit | `uv run pytest tests/unit/test_rag/test_pdf_processor.py::test_page_references -x` | Wave 0 |
| DATA-05 | bge-m3 embedding generation returns 1024-dim vectors | unit | `uv run pytest tests/unit/test_rag/test_embeddings.py::test_embedding_dimensions -x` | Wave 0 |
| DATA-05 | Embedding batch processing works | unit | `uv run pytest tests/unit/test_rag/test_embeddings.py::test_batch_embedding -x` | Wave 0 |
| DATA-06 | Qdrant collection creation and upsert | integration | `uv run pytest tests/integration/test_rag_vector_store.py::test_upsert_and_search -x` | Wave 0 |
| DATA-06 | Metadata filtering by ticker/year | integration | `uv run pytest tests/integration/test_rag_vector_store.py::test_filtered_search -x` | Wave 0 |
| DATA-07 | Search returns parent context with child match | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_parent_child_retrieval -x` | Wave 0 |
| DATA-07 | Source page references in results | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_page_reference_in_results -x` | Wave 0 |
| DATA-07 | Score threshold filtering works | unit | `uv run pytest tests/unit/test_rag/test_retriever.py::test_score_threshold -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_rag/ tests/unit/test_api/test_documents_routes.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x --cov=stockvaluefinder --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_rag/test_pdf_processor.py` -- covers DATA-04 chunking, tables, page refs
- [ ] `tests/unit/test_rag/test_embeddings.py` -- covers DATA-05 embedding generation
- [ ] `tests/unit/test_rag/test_retriever.py` -- covers DATA-07 search, parent-child, threshold
- [ ] `tests/unit/test_api/test_documents_routes.py` -- covers DATA-03 upload endpoint
- [ ] `tests/integration/test_rag_vector_store.py` -- covers DATA-06 Qdrant integration
- [ ] PyMuPDF install: `uv add pymupdf` -- required before any PDF test

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user MVP per Out of Scope |
| V3 Session Management | no | Single-user MVP |
| V4 Access Control | no | Single-user MVP |
| V5 Input Validation | yes | Pydantic BaseModel with Field validation for all inputs; ticker regex pattern; file type validation |
| V6 Cryptography | no | No encryption needed for this phase |
| V8 Data Protection | yes | API keys via env vars (OPENROUTER_API_KEY); file upload size limits (100MB max) |

### Known Threat Patterns for RAG Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious PDF upload | Tampering | Validate PDF structure with PyMuPDF; limit file size; scan for known exploit patterns |
| Path traversal via filename | Tampering | Sanitize filename; use UUID-based storage paths; never use user-provided filename directly |
| Embedding API key exposure | Information Disclosure | Store in env var; never log; use `.env` file (gitignored) |
| Prompt injection via PDF content | Tampering | Multi-query expansion uses LLM; sanitize query inputs; do not execute PDF content as code |
| DoS via large file upload | Denial of Service | File size limit (100MB); request timeout; rate limiting on upload endpoint |

## Sources

### Primary (HIGH confidence)
- PyPI registry -- verified package versions (pymupdf 1.27.2.2, qdrant-client 1.17.1, tiktoken 0.12.0)
- PyMuPDF documentation (pymupdf.readthedocs.io) -- `find_tables()`, `get_text()`, page structure API
- OpenRouter bge-m3 model page (openrouter.ai/baai/bge-m3) -- pricing, API format, dimensions
- Qdrant Python client GitHub (github.com/qdrant/qdrant-client) -- collection creation, upsert, search, payload filtering
- Codebase analysis -- existing patterns, dependencies, config structure

### Secondary (MEDIUM confidence)
- Together AI documentation (docs.together.ai/reference/embeddings) -- confirmed bge-m3 NOT available on Together AI
- WebSearch results for parent-child chunking pattern (multiple sources agree)
- WebSearch results for bge-m3 model specifications (1024-dim, 8192 context, 100+ languages)

### Tertiary (LOW confidence)
- [ASSUMED] tiktoken cl100k_base is a reasonable approximation for bge-m3 token counting
- [ASSUMED] Single Qdrant collection scales for MVP (300 stocks x ~10 docs)
- [ASSUMED] PyMuPDF handles Chinese annual report PDFs without issues in most cases

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages verified on PyPI, versions confirmed, compatibility checked
- Architecture: HIGH - parent-child pattern well-documented, Qdrant API verified from official sources
- Pitfalls: MEDIUM - based on RAG community knowledge and official docs, not all tested with Chinese annual reports specifically

**Research date:** 2026-04-18
**Valid until:** 2026-05-18 (30 days - stable libraries, may need refresh for pricing changes)
