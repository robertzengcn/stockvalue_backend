"""Tests for UserStockAccessDB ORM model and Pydantic schemas."""

import os
import pytest
from datetime import datetime
from uuid import uuid4

# Set DATABASE_URL before importing any modules that use db.base
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from pydantic import ValidationError

from stockvaluefinder.db.models.user_stock_access import UserStockAccessDB
from stockvaluefinder.models.user_stock_access import (
    StockAccessEntry,
    StockAccessListResponse,
    StockAccessUpdateRequest,
    StockAccessAddRequest,
    StockAccessRemoveRequest,
)


class TestUserStockAccessDBModel:
    """Tests for UserStockAccessDB ORM model."""

    def test_tablename_is_user_stock_access(self) -> None:
        """Test 1: UserStockAccessDB has correct tablename 'user_stock_access'."""
        assert UserStockAccessDB.__tablename__ == "user_stock_access"

    def test_model_has_required_columns(self) -> None:
        """Test: UserStockAccessDB has all required columns."""
        column_names = {col.name for col in UserStockAccessDB.__table__.columns}
        assert "id" in column_names
        assert "user_id" in column_names
        assert "ticker" in column_names
        assert "created_at" in column_names

    def test_user_id_has_foreign_key_to_users(self) -> None:
        """Test: user_id column has FK constraint to users.id."""
        user_id_col = UserStockAccessDB.__table__.columns["user_id"]
        fks = list(user_id_col.foreign_keys)
        assert len(fks) == 1
        assert "users.id" in str(fks[0].target_fullname)

    def test_unique_constraint_on_user_id_ticker(self) -> None:
        """Test: UniqueConstraint exists on (user_id, ticker)."""
        constraint_names = {
            c.name  # type: ignore[union-attr]
            for c in UserStockAccessDB.__table__.constraints  # type: ignore[attr-defined]
            if hasattr(c, "name")
        }
        assert "uq_user_stock_access_user_ticker" in constraint_names

    def test_repr(self) -> None:
        """Test: __repr__ returns expected format."""
        obj = UserStockAccessDB(user_id="test-user-id", ticker="600519.SH")
        assert (
            repr(obj) == "<UserStockAccessDB(user_id=test-user-id, ticker=600519.SH)>"
        )


class TestStockAccessEntry:
    """Tests for StockAccessEntry Pydantic model."""

    def test_valid_ticker_passes_validation(self) -> None:
        """Test 2: StockAccessEntry validates ticker format (SH)."""
        entry = StockAccessEntry(ticker="600519.SH", created_at=datetime.utcnow())
        assert entry.ticker == "600519.SH"

    def test_valid_sz_ticker(self) -> None:
        """Test: SZ ticker format is accepted."""
        entry = StockAccessEntry(ticker="000001.SZ", created_at=datetime.utcnow())
        assert entry.ticker == "000001.SZ"

    def test_valid_hk_ticker(self) -> None:
        """Test: HK ticker format is accepted (6-digit per project convention)."""
        entry = StockAccessEntry(ticker="000070.HK", created_at=datetime.utcnow())
        assert entry.ticker == "000070.HK"

    def test_invalid_ticker_rejected(self) -> None:
        """Test: Invalid ticker format raises ValidationError."""
        with pytest.raises(ValidationError):
            StockAccessEntry(ticker="INVALID", created_at=datetime.utcnow())

    def test_ticker_without_dot_rejected(self) -> None:
        """Test 4: Ticker without dot (e.g., '600519') is rejected."""
        with pytest.raises(ValidationError):
            StockAccessEntry(ticker="600519", created_at=datetime.utcnow())

    def test_lowercase_ticker_rejected(self) -> None:
        """Test: Lowercase exchange suffix is rejected."""
        with pytest.raises(ValidationError):
            StockAccessEntry(ticker="600519.sh", created_at=datetime.utcnow())


class TestStockAccessListResponse:
    """Tests for StockAccessListResponse Pydantic model."""

    def test_contains_user_id_and_tickers(self) -> None:
        """Test 3: StockAccessListResponse has user_id and list of StockAccessEntry."""
        now = datetime.utcnow()
        user_id = uuid4()
        entries = [
            StockAccessEntry(ticker="600519.SH", created_at=now),
            StockAccessEntry(ticker="000001.SZ", created_at=now),
        ]
        response = StockAccessListResponse(user_id=user_id, tickers=entries)
        assert response.user_id == user_id
        assert len(response.tickers) == 2
        assert response.tickers[0].ticker == "600519.SH"

    def test_empty_tickers_default(self) -> None:
        """Test: Empty tickers list is valid default."""
        user_id = uuid4()
        response = StockAccessListResponse(user_id=user_id)
        assert response.tickers == []


class TestStockAccessUpdateRequest:
    """Tests for StockAccessUpdateRequest Pydantic model."""

    def test_valid_tickers_list(self) -> None:
        """Test: Valid list of tickers passes validation."""
        req = StockAccessUpdateRequest(tickers=["600519.SH", "000001.SZ"])
        assert len(req.tickers) == 2

    def test_empty_tickers_rejected(self) -> None:
        """Test: Empty tickers list is rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            StockAccessUpdateRequest(tickers=[])

    def test_invalid_ticker_in_list_rejected(self) -> None:
        """Test: Invalid ticker format in list is rejected."""
        with pytest.raises(ValidationError):
            StockAccessUpdateRequest(tickers=["600519.SH", "INVALID"])


class TestStockAccessAddRequest:
    """Tests for StockAccessAddRequest Pydantic model."""

    def test_valid_ticker(self) -> None:
        """Test: Valid ticker passes validation."""
        req = StockAccessAddRequest(ticker="600519.SH")
        assert req.ticker == "600519.SH"

    def test_invalid_ticker_rejected(self) -> None:
        """Test: Invalid ticker is rejected."""
        with pytest.raises(ValidationError):
            StockAccessAddRequest(ticker="bad-format")


class TestStockAccessRemoveRequest:
    """Tests for StockAccessRemoveRequest Pydantic model."""

    def test_valid_ticker(self) -> None:
        """Test: Valid ticker passes validation."""
        req = StockAccessRemoveRequest(ticker="600519.SH")
        assert req.ticker == "600519.SH"

    def test_invalid_ticker_rejected(self) -> None:
        """Test: Invalid ticker is rejected."""
        with pytest.raises(ValidationError):
            StockAccessRemoveRequest(ticker="bad-format")


class TestMigration017:
    """Tests for Alembic migration 017 file."""

    def _load_migration_module(self):
        """Load migration module via importlib with correct path."""
        import importlib.util
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "alembic",
            "versions",
            "017_user_stock_access_table.py",
        )
        migration_path = os.path.normpath(migration_path)
        spec = importlib.util.spec_from_file_location("migration_017", migration_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_migration_file_exists(self) -> None:
        """Test 4: Migration 017 file exists."""
        mod = self._load_migration_module()
        assert mod is not None

    def test_migration_revision_chain(self) -> None:
        """Test: Migration 017 has correct revision chain (016 -> 017)."""
        mod = self._load_migration_module()
        assert mod.revision == "017"
        assert mod.down_revision == "016"

    def test_migration_has_upgrade_and_downgrade(self) -> None:
        """Test: Migration has both upgrade and downgrade functions."""
        mod = self._load_migration_module()
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)
