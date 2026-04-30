---
wave: 1
depends_on: [04-01]
files_modified:
  - stockvaluefinder/db/models/document.py
  - stockvaluefinder/alembic/versions/*
  - stockvaluefinder/models/document.py
  - stockvaluefinder/repositories/document_repo.py
must_haves:
  truths:
    - DocumentDB ORM model exists with all 9 fields
    - Alembic migration created and valid
    - Pydantic models for chunks and responses defined
    - DocumentRepository with CRUD operations
  artifacts:
    - stockvaluefinder/db/models/document.py
    - stockvaluefinder/alembic/versions/*_add_documents_table.py
    - stockvaluefinder/models/document.py
    - stockvaluefinder/repositories/document_repo.py
  key_links:
    - DocumentDB maps to documents table
    - Pydantic models serialize/deserialize chunk data
    - DocumentRepository operates on DocumentDB
requirements: DATA-03 (partial), DATA-06 (partial)
---

# Phase 4 Plan 01B: Database Models & Repository

**Goal:** Create Document ORM model, migration, Pydantic models, and repository.

## Tasks

<Task id="04-01B-01">
<action>Create SQLAlchemy ORM model for Document in db/models/document.py with fields: document_id (String 36, PK, UUID default), ticker (String 20, nullable=False, indexed), file_name (String 500, nullable=False), file_path (String 1000, nullable=False), page_count (Integer, nullable=False), processing_status (String 20, nullable=False, default="pending"), metadata_ (JSONB, nullable=False, default=dict), created_at (DateTime, nullable=False), updated_at (DateTime, nullable=False, onupdate)</action>
<read_first>
- stockvaluefinder/db/models/stock.py (existing model pattern)
- stockvaluefinder/db/models/financial.py (JSONB column pattern)
- stockvaluefinder/db/base.py (Base class import)
</read_first>
<acceptance_criteria>
- db/models/document.py exists with `class DocumentDB(Base):`
- All 9 fields defined with correct types and constraints
- __tablename__ = "documents"
- Model passes mypy: `uv run mypy stockvaluefinder/db/models/document.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run mypy stockvaluefinder/db/models/document.py</automated>
</verify>
<done>
- DocumentDB model created
- mypy passes
</done>
</Task>

<Task id="04-01B-02">
<action>Create Alembic migration for documents table: run `uv run alembic revision --autogenerate -m "add documents table"` and verify migration file contains create_table("documents") with all 9 columns</action>
<read_first>
- stockvaluefinder/alembic/env.py (migration configuration)
- stockvaluefinder/db/models/document.py (new model)
- alembic/versions/ (existing migration patterns)
</read_first>
<acceptance_criteria>
- New migration file exists in alembic/versions/ with timestamp prefix
- Migration contains `op.create_table('documents', ...)`
- Migration contains all 9 columns with correct types
- Migration down() contains `op.drop_table('documents')`
- Command `uv run alembic check` exits 0
</acceptance_criteria>
<verify>
<automated>uv run alembic check</automated>
</verify>
<done>
- Migration file created
- alembic check passes
</done>
</Task>

<Task id="04-01B-03">
<action>Create Pydantic models in models/document.py: DocumentChunk (chunk_id, content, metadata), ChunkMetadata (document_id, parent_id, page_number, section, ticker, year, report_type, company_name, filing_date, chunk_type, token_count), DocumentUploadResponse (document_id, status, chunk_count, page_count), DocumentSearchRequest (query, ticker, year, limit, score_threshold, use_multi_query). All models frozen with model_config={"frozen": True}</action>
<read_first>
- stockvaluefinder/models/api.py (ApiResponse pattern, frozen config)
- stockvaluefinder/models/valuation.py (request/response models)
</read_first>
<acceptance_criteria>
- models/document.py exists with all 4 model classes
- ChunkMetadata and DocumentChunk are frozen dataclasses
- DocumentUploadResponse and DocumentSearchRequest are frozen Pydantic models
- All models have type hints for all fields
- mypy passes: `uv run mypy stockvaluefinder/models/document.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run mypy stockvaluefinder/models/document.py</automated>
</verify>
<done>
- All 4 Pydantic models created
- mypy passes
</done>
</Task>

<Task id="04-01B-04">
<action>Create DocumentRepository in repositories/document_repo.py extending BaseRepository with methods: get_by_ticker(session, ticker), get_by_document_id(session, document_id), get_by_status(session, status), create(session, ticker, file_name, file_path, page_count, metadata), update_status(session, document_id, status), update_metadata(session, document_id, metadata)</action>
<read_first>
- stockvaluefinder/repositories/base.py (BaseRepository pattern)
- stockvaluefinder/repositories/stock_repo.py (simple CRUD example)
- stockvaluefinder/db/models/document.py (ORM model)
- stockvaluefinder/models/document.py (Pydantic models)
</read_first>
<acceptance_criteria>
- repositories/document_repo.py exists with `class DocumentRepository(BaseRepository[DocumentDB, ...])`
- All 6 methods implemented with proper async/await
- Methods use session.query() or session.execute() pattern from base
- Type hints on all method signatures
- mypy passes: `uv run mypy stockvaluefinder/repositories/document_repo.py` exits 0
</acceptance_criteria>
<verify>
<automated>uv run mypy stockvaluefinder/repositories/document_repo.py</automated>
</verify>
<done>
- DocumentRepository created with 6 methods
- mypy passes
</done>
</Task>

## Verification

After completing this wave:
- [ ] `uv run mypy stockvaluefinder/db/models/document.py stockvaluefinder/models/document.py stockvaluefinder/repositories/document_repo.py` exits 0
- [ ] `uv run alembic check` exits 0

## Threat Model

| Threat | STRIDE | Mitigation | Implemented In |
|--------|--------|------------|----------------|
| Path traversal via filename | Tampering | Sanitize filename, use UUID-based storage paths | Task 04-01B-01 (file_name stored separately from file_path) |
| SQL injection | Tampering | Parameterized queries via SQLAlchemy ORM | Task 04-01B-04 (BaseRepository uses ORM) |
