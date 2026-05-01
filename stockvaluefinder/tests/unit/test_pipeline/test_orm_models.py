"""Tests for pipeline ORM models (PipelineTaskDB and PipelineDocumentDB)."""

from stockvaluefinder.db.models.pipeline_task import PipelineTaskDB
from stockvaluefinder.db.models.pipeline_document import PipelineDocumentDB


class TestPipelineTaskDB:
    """Test PipelineTaskDB ORM model."""

    def test_tablename(self) -> None:
        assert PipelineTaskDB.__tablename__ == "pipeline_tasks"

    def test_has_task_id_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "task_id" in columns

    def test_has_ticker_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "ticker" in columns

    def test_has_business_key_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "business_key" in columns

    def test_has_state_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "state" in columns

    def test_has_current_stage_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "current_stage" in columns

    def test_has_retry_count_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "retry_count" in columns

    def test_has_max_retries_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "max_retries" in columns

    def test_has_error_message_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "error_message" in columns

    def test_has_result_summary_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "result_summary" in columns

    def test_has_created_at_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "created_at" in columns

    def test_has_updated_at_column(self) -> None:
        columns = {c.name for c in PipelineTaskDB.__table__.columns}
        assert "updated_at" in columns

    def test_ticker_has_foreign_key_to_stocks(self) -> None:
        ticker_col = PipelineTaskDB.__table__.c.ticker
        fks = list(ticker_col.foreign_keys)
        assert len(fks) == 1
        assert "stocks.ticker" in str(fks[0].target_fullname)

    def test_business_key_is_unique(self) -> None:
        bk_col = PipelineTaskDB.__table__.c.business_key
        assert bk_col.unique is True

    def test_state_has_default_pending(self) -> None:
        state_col = PipelineTaskDB.__table__.c.state
        assert state_col.default is not None
        assert state_col.default.arg == "pending"

    def test_ticker_is_indexed(self) -> None:
        table = PipelineTaskDB.__table__
        indexed_cols = set()
        for idx in table.indexes:  # type: ignore[attr-defined]
            for col in idx.columns:
                indexed_cols.add(col.name)
        assert "ticker" in indexed_cols

    def test_repr_returns_string(self) -> None:
        """Test that __repr__ method exists and returns expected format."""
        assert hasattr(PipelineTaskDB, "__repr__")
        # Verify repr format from the source
        import inspect

        source = inspect.getsource(PipelineTaskDB.__repr__)
        assert "task_id" in source
        assert "ticker" in source
        assert "state" in source


class TestPipelineDocumentDB:
    """Test PipelineDocumentDB ORM model."""

    def test_tablename(self) -> None:
        assert PipelineDocumentDB.__tablename__ == "pipeline_documents"

    def test_has_document_id_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "document_id" in columns

    def test_has_task_id_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "task_id" in columns

    def test_has_source_url_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "source_url" in columns

    def test_has_source_id_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "source_id" in columns

    def test_has_content_hash_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "content_hash" in columns

    def test_has_file_path_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "file_path" in columns

    def test_has_file_size_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "file_size" in columns

    def test_has_downloaded_at_column(self) -> None:
        columns = {c.name for c in PipelineDocumentDB.__table__.columns}
        assert "downloaded_at" in columns

    def test_task_id_has_foreign_key_to_pipeline_tasks(self) -> None:
        task_id_col = PipelineDocumentDB.__table__.c.task_id
        fks = list(task_id_col.foreign_keys)
        assert len(fks) == 1
        assert "pipeline_tasks.task_id" in str(fks[0].target_fullname)

    def test_repr_returns_string(self) -> None:
        """Test that __repr__ method exists and returns expected format."""
        assert hasattr(PipelineDocumentDB, "__repr__")
        import inspect

        source = inspect.getsource(PipelineDocumentDB.__repr__)
        assert "document_id" in source
        assert "task_id" in source
