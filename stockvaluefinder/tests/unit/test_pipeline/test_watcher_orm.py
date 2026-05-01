"""Tests for watcher ORM models (WatchlistDB, WatcherStateDB, PendingDisclosureDB)."""

import inspect

import pytest

from stockvaluefinder.db.models import (
    PendingDisclosureDB,
    WatcherStateDB,
    WatchlistDB,
)


class TestWatchlistDB:
    """Test WatchlistDB ORM model (D-13)."""

    def test_tablename(self) -> None:
        assert WatchlistDB.__tablename__ == "watchlist"

    def test_has_ticker_column(self) -> None:
        columns = {c.name for c in WatchlistDB.__table__.columns}
        assert "ticker" in columns

    def test_has_name_column(self) -> None:
        columns = {c.name for c in WatchlistDB.__table__.columns}
        assert "name" in columns

    def test_has_added_at_column(self) -> None:
        columns = {c.name for c in WatchlistDB.__table__.columns}
        assert "added_at" in columns

    def test_has_is_active_column(self) -> None:
        columns = {c.name for c in WatchlistDB.__table__.columns}
        assert "is_active" in columns

    def test_ticker_is_primary_key(self) -> None:
        pk_cols = [c.name for c in WatchlistDB.__table__.primary_key.columns]  # type: ignore[attr-defined]
        assert "ticker" in pk_cols

    def test_ticker_is_string_20(self) -> None:
        ticker_col = WatchlistDB.__table__.c.ticker
        assert ticker_col.type.length == 20  # type: ignore[attr-defined]

    def test_name_is_string_100(self) -> None:
        name_col = WatchlistDB.__table__.c.name
        assert name_col.type.length == 100  # type: ignore[attr-defined]

    def test_is_active_default_true(self) -> None:
        active_col = WatchlistDB.__table__.c.is_active
        assert active_col.default is not None
        assert active_col.default.arg is True

    def test_added_at_is_datetime_with_timezone(self) -> None:
        added_at_col = WatchlistDB.__table__.c.added_at
        assert added_at_col.type.timezone is True  # type: ignore[attr-defined]

    def test_repr_returns_string(self) -> None:
        assert hasattr(WatchlistDB, "__repr__")
        source = inspect.getsource(WatchlistDB.__repr__)
        assert "ticker" in source
        assert "name" in source


class TestWatcherStateDB:
    """Test WatcherStateDB ORM model (D-16)."""

    def test_tablename(self) -> None:
        assert WatcherStateDB.__tablename__ == "watcher_state"

    def test_has_watcher_id_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "watcher_id" in columns

    def test_has_last_poll_time_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "last_poll_time" in columns

    def test_has_last_akshare_success_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "last_akshare_success" in columns

    def test_has_last_cninfo_fallback_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "last_cninfo_fallback" in columns

    def test_has_polls_count_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "polls_count" in columns

    def test_has_errors_count_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "errors_count" in columns

    def test_has_updated_at_column(self) -> None:
        columns = {c.name for c in WatcherStateDB.__table__.columns}
        assert "updated_at" in columns

    def test_watcher_id_is_primary_key(self) -> None:
        pk_cols = [c.name for c in WatcherStateDB.__table__.primary_key.columns]  # type: ignore[attr-defined]
        assert "watcher_id" in pk_cols

    def test_watcher_id_default_is_default_string(self) -> None:
        watcher_id_col = WatcherStateDB.__table__.c.watcher_id
        assert watcher_id_col.default is not None
        assert watcher_id_col.default.arg == "default"

    def test_last_poll_time_is_nullable(self) -> None:
        col = WatcherStateDB.__table__.c.last_poll_time
        assert col.nullable is True

    def test_last_akshare_success_default_false(self) -> None:
        col = WatcherStateDB.__table__.c.last_akshare_success
        assert col.default is not None
        assert col.default.arg is False

    def test_polls_count_default_zero(self) -> None:
        col = WatcherStateDB.__table__.c.polls_count
        assert col.default is not None
        assert col.default.arg == 0

    def test_errors_count_default_zero(self) -> None:
        col = WatcherStateDB.__table__.c.errors_count
        assert col.default is not None
        assert col.default.arg == 0

    def test_repr_returns_string(self) -> None:
        assert hasattr(WatcherStateDB, "__repr__")
        source = inspect.getsource(WatcherStateDB.__repr__)
        assert "watcher_id" in source


class TestPendingDisclosureDB:
    """Test PendingDisclosureDB ORM model (D-11)."""

    def test_tablename(self) -> None:
        assert PendingDisclosureDB.__tablename__ == "pending_disclosures"

    def test_has_disclosure_id_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "disclosure_id" in columns

    def test_has_poll_id_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "poll_id" in columns

    def test_has_ticker_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "ticker" in columns

    def test_has_stock_name_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "stock_name" in columns

    def test_has_report_type_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "report_type" in columns

    def test_has_fiscal_year_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "fiscal_year" in columns

    def test_has_disclosure_date_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "disclosure_date" in columns

    def test_has_first_appointment_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "first_appointment" in columns

    def test_has_source_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "source" in columns

    def test_has_source_raw_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "source_raw" in columns

    def test_has_processed_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "processed" in columns

    def test_has_created_at_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "created_at" in columns

    def test_has_processed_at_column(self) -> None:
        columns = {c.name for c in PendingDisclosureDB.__table__.columns}
        assert "processed_at" in columns

    def test_disclosure_id_is_primary_key(self) -> None:
        pk_cols = [c.name for c in PendingDisclosureDB.__table__.primary_key.columns]  # type: ignore[attr-defined]
        assert "disclosure_id" in pk_cols

    def test_disclosure_id_is_uuid(self) -> None:
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID

        col = PendingDisclosureDB.__table__.c.disclosure_id
        assert isinstance(col.type, PG_UUID)

    def test_poll_id_is_not_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.poll_id
        assert col.nullable is False

    def test_ticker_is_not_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.ticker
        assert col.nullable is False

    def test_report_type_is_not_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.report_type
        assert col.nullable is False

    def test_fiscal_year_is_not_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.fiscal_year
        assert col.nullable is False

    def test_source_is_not_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.source
        assert col.nullable is False

    def test_stock_name_is_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.stock_name
        assert col.nullable is True

    def test_disclosure_date_is_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.disclosure_date
        assert col.nullable is True

    def test_source_raw_is_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.source_raw
        assert col.nullable is True

    def test_processed_at_is_nullable(self) -> None:
        col = PendingDisclosureDB.__table__.c.processed_at
        assert col.nullable is True

    def test_processed_default_false(self) -> None:
        col = PendingDisclosureDB.__table__.c.processed
        assert col.default is not None
        assert col.default.arg is False

    def test_poll_id_is_indexed(self) -> None:
        table = PendingDisclosureDB.__table__
        indexed_cols = set()
        for idx in table.indexes:  # type: ignore[attr-defined]
            for col in idx.columns:
                indexed_cols.add(col.name)
        assert "poll_id" in indexed_cols

    def test_processed_is_indexed(self) -> None:
        table = PendingDisclosureDB.__table__
        indexed_cols = set()
        for idx in table.indexes:  # type: ignore[attr-defined]
            for col in idx.columns:
                indexed_cols.add(col.name)
        assert "processed" in indexed_cols

    def test_repr_returns_string(self) -> None:
        assert hasattr(PendingDisclosureDB, "__repr__")
        source = inspect.getsource(PendingDisclosureDB.__repr__)
        assert "disclosure_id" in source


class TestModelsExport:
    """Test that db/models/__init__.py exports the new models."""

    def test_watchlist_db_importable(self) -> None:
        from stockvaluefinder.db.models import WatchlistDB

        assert WatchlistDB is not None

    def test_watcher_state_db_importable(self) -> None:
        from stockvaluefinder.db.models import WatcherStateDB

        assert WatcherStateDB is not None

    def test_pending_disclosure_db_importable(self) -> None:
        from stockvaluefinder.db.models import PendingDisclosureDB

        assert PendingDisclosureDB is not None

    def test_watchlist_db_in_all(self) -> None:
        from stockvaluefinder.db.models import __all__

        assert "WatchlistDB" in __all__

    def test_watcher_state_db_in_all(self) -> None:
        from stockvaluefinder.db.models import __all__

        assert "WatcherStateDB" in __all__

    def test_pending_disclosure_db_in_all(self) -> None:
        from stockvaluefinder.db.models import __all__

        assert "PendingDisclosureDB" in __all__


class TestMigration010:
    """Test Alembic migration 010 creates correct tables."""

    @pytest.fixture()
    def migration_source(self) -> str:
        """Read migration 010 source file."""
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "alembic",
            "versions",
            "010_watcher_tables.py",
        )
        with open(migration_path) as f:
            return f.read()

    def test_migration_file_exists(self) -> None:
        """Migration 010 file exists in alembic/versions/."""
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "alembic",
            "versions",
            "010_watcher_tables.py",
        )
        assert os.path.isfile(migration_path)

    def test_migration_has_down_revision_009(self, migration_source: str) -> None:
        """Migration 010 has down_revision = '009'."""
        assert "down_revision" in migration_source
        assert '"009"' in migration_source

    def test_migration_revision_is_010(self, migration_source: str) -> None:
        """Migration 010 has revision = '010'."""
        assert "revision" in migration_source
        assert '"010"' in migration_source

    def test_migration_has_upgrade_function(self, migration_source: str) -> None:
        """Migration 010 has upgrade function."""
        assert "def upgrade(" in migration_source

    def test_migration_has_downgrade_function(self, migration_source: str) -> None:
        """Migration 010 has downgrade function."""
        assert "def downgrade(" in migration_source

    def test_upgrade_creates_all_three_tables(self, migration_source: str) -> None:
        """Upgrade function references all 3 table names."""
        assert '"watchlist"' in migration_source
        assert '"watcher_state"' in migration_source
        assert '"pending_disclosures"' in migration_source

    def test_downgrade_drops_all_three_tables(self, migration_source: str) -> None:
        """Downgrade function drops all 3 tables."""
        assert '"pending_disclosures"' in migration_source
        assert '"watcher_state"' in migration_source
        assert '"watchlist"' in migration_source

    def test_downgrade_drops_in_reverse_order(self, migration_source: str) -> None:
        """Downgrade drops pending_disclosures first, then watcher_state, then watchlist."""
        # Find the downgrade function portion
        downgrade_start = migration_source.index("def downgrade(")
        downgrade_source = migration_source[downgrade_start:]
        pos_pending = downgrade_source.index('"pending_disclosures"')
        pos_watcher = downgrade_source.index('"watcher_state"')
        pos_watchlist = downgrade_source.index('"watchlist"')
        assert pos_pending < pos_watcher < pos_watchlist
