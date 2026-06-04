"""Tests for market scanner ORM models, migration, and __init__ exports.

TDD RED phase: Tests written before implementation.
Covers: ORM model structure (table names, columns, constraints, indexes),
and __init__.py export registration.
"""

from sqlalchemy import inspect

from stockvaluefinder.db.models import (
    IndexConstituentDB,
    MarketScanCandidateDB,
    MarketScanRuleDB,
    MarketScanRunDB,
)


class TestIndexConstituentDB:
    """Test IndexConstituentDB ORM model structure."""

    def test_tablename(self) -> None:
        """IndexConstituentDB must use table name 'index_constituents'."""
        assert IndexConstituentDB.__tablename__ == "index_constituents"

    def test_has_constituent_id_pk(self) -> None:
        """IndexConstituentDB must have constituent_id as UUID primary key."""
        mapper = inspect(IndexConstituentDB)
        pk_cols = [c.name for c in mapper.primary_key]
        assert "constituent_id" in pk_cols

    def test_has_index_code_column(self) -> None:
        """IndexConstituentDB must have index_code column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "index_code" in col_names

    def test_has_ticker_column(self) -> None:
        """IndexConstituentDB must have ticker column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "ticker" in col_names

    def test_has_name_column(self) -> None:
        """IndexConstituentDB must have name column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "name" in col_names

    def test_has_effective_date_column(self) -> None:
        """IndexConstituentDB must have effective_date column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "effective_date" in col_names

    def test_has_removed_date_column(self) -> None:
        """IndexConstituentDB must have removed_date column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "removed_date" in col_names

    def test_has_is_active_column(self) -> None:
        """IndexConstituentDB must have is_active column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "is_active" in col_names

    def test_has_source_column(self) -> None:
        """IndexConstituentDB must have source column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "source" in col_names

    def test_has_created_at_column(self) -> None:
        """IndexConstituentDB must have created_at column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "created_at" in col_names

    def test_has_updated_at_column(self) -> None:
        """IndexConstituentDB must have updated_at column."""
        mapper = inspect(IndexConstituentDB)
        col_names = [c.name for c in mapper.columns]
        assert "updated_at" in col_names

    def test_has_unique_constraint_index_code_ticker_date(self) -> None:
        """IndexConstituentDB must have UniqueConstraint on (index_code, ticker, effective_date)."""
        constraint_names = [
            c.name for c in IndexConstituentDB.__table_args__ if hasattr(c, "name")
        ]
        assert "uq_idx_ticker_date" in constraint_names


class TestMarketScanRunDB:
    """Test MarketScanRunDB ORM model structure."""

    def test_tablename(self) -> None:
        """MarketScanRunDB must use table name 'market_scan_runs'."""
        assert MarketScanRunDB.__tablename__ == "market_scan_runs"

    def test_has_run_id_pk(self) -> None:
        """MarketScanRunDB must have run_id as UUID primary key."""
        mapper = inspect(MarketScanRunDB)
        pk_cols = [c.name for c in mapper.primary_key]
        assert "run_id" in pk_cols

    def test_has_index_codes_column(self) -> None:
        """MarketScanRunDB must have index_codes JSONB column."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "index_codes" in col_names

    def test_has_scan_type_column(self) -> None:
        """MarketScanRunDB must have scan_type column."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "scan_type" in col_names

    def test_has_status_column(self) -> None:
        """MarketScanRunDB must have status column with default 'pending'."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "status" in col_names

    def test_has_rules_version_column(self) -> None:
        """MarketScanRunDB must have rules_version column."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "rules_version" in col_names

    def test_has_count_columns(self) -> None:
        """MarketScanRunDB must have total_count, screened_count, candidate_count."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "total_count" in col_names
        assert "screened_count" in col_names
        assert "candidate_count" in col_names

    def test_has_error_summary_column(self) -> None:
        """MarketScanRunDB must have error_summary JSONB column."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "error_summary" in col_names

    def test_has_timestamps(self) -> None:
        """MarketScanRunDB must have started_at, completed_at, created_at, updated_at."""
        mapper = inspect(MarketScanRunDB)
        col_names = [c.name for c in mapper.columns]
        assert "started_at" in col_names
        assert "completed_at" in col_names
        assert "created_at" in col_names
        assert "updated_at" in col_names

    def test_status_indexed(self) -> None:
        """MarketScanRunDB status column must be indexed."""
        mapper = inspect(MarketScanRunDB)
        status_col = mapper.columns["status"]
        assert status_col.index is True


class TestMarketScanCandidateDB:
    """Test MarketScanCandidateDB ORM model structure."""

    def test_tablename(self) -> None:
        """MarketScanCandidateDB must use table name 'market_scan_candidates'."""
        assert MarketScanCandidateDB.__tablename__ == "market_scan_candidates"

    def test_has_candidate_id_pk(self) -> None:
        """MarketScanCandidateDB must have candidate_id as UUID primary key."""
        mapper = inspect(MarketScanCandidateDB)
        pk_cols = [c.name for c in mapper.primary_key]
        assert "candidate_id" in pk_cols

    def test_has_run_id_fk(self) -> None:
        """MarketScanCandidateDB must have run_id FK to market_scan_runs."""
        mapper = inspect(MarketScanCandidateDB)
        col_names = [c.name for c in mapper.columns]
        assert "run_id" in col_names

    def test_has_ticker_column(self) -> None:
        """MarketScanCandidateDB must have ticker column."""
        mapper = inspect(MarketScanCandidateDB)
        col_names = [c.name for c in mapper.columns]
        assert "ticker" in col_names

    def test_has_passed_column(self) -> None:
        """MarketScanCandidateDB must have passed boolean column."""
        mapper = inspect(MarketScanCandidateDB)
        col_names = [c.name for c in mapper.columns]
        assert "passed" in col_names

    def test_has_composite_score_column(self) -> None:
        """MarketScanCandidateDB must have composite_score float column."""
        mapper = inspect(MarketScanCandidateDB)
        col_names = [c.name for c in mapper.columns]
        assert "composite_score" in col_names

    def test_has_screening_snapshot_column(self) -> None:
        """MarketScanCandidateDB must have screening_snapshot JSONB column."""
        mapper = inspect(MarketScanCandidateDB)
        col_names = [c.name for c in mapper.columns]
        assert "screening_snapshot" in col_names

    def test_has_unique_constraint_run_ticker(self) -> None:
        """MarketScanCandidateDB must have UniqueConstraint on (run_id, ticker)."""
        constraint_names = [
            c.name for c in MarketScanCandidateDB.__table_args__ if hasattr(c, "name")
        ]
        assert "uq_candidate_run_ticker" in constraint_names


class TestMarketScanRuleDB:
    """Test MarketScanRuleDB ORM model structure."""

    def test_tablename(self) -> None:
        """MarketScanRuleDB must use table name 'market_scan_rules'."""
        assert MarketScanRuleDB.__tablename__ == "market_scan_rules"

    def test_has_rule_id_pk(self) -> None:
        """MarketScanRuleDB must have rule_id as UUID primary key."""
        mapper = inspect(MarketScanRuleDB)
        pk_cols = [c.name for c in mapper.primary_key]
        assert "rule_id" in pk_cols

    def test_has_rule_name_unique(self) -> None:
        """MarketScanRuleDB must have rule_name as unique column."""
        mapper = inspect(MarketScanRuleDB)
        rule_name_col = mapper.columns["rule_name"]
        assert rule_name_col.unique is True

    def test_has_rule_type_column(self) -> None:
        """MarketScanRuleDB must have rule_type column."""
        mapper = inspect(MarketScanRuleDB)
        col_names = [c.name for c in mapper.columns]
        assert "rule_type" in col_names

    def test_has_is_active_column(self) -> None:
        """MarketScanRuleDB must have is_active boolean column."""
        mapper = inspect(MarketScanRuleDB)
        col_names = [c.name for c in mapper.columns]
        assert "is_active" in col_names

    def test_has_parameters_column(self) -> None:
        """MarketScanRuleDB must have parameters JSONB column."""
        mapper = inspect(MarketScanRuleDB)
        col_names = [c.name for c in mapper.columns]
        assert "parameters" in col_names


class TestInitExports:
    """Test that __init__.py exports all 4 new ORM models."""

    def test_exports_index_constituent_db(self) -> None:
        """db/models/__init__.py must export IndexConstituentDB."""
        from stockvaluefinder.db.models import __all__

        assert "IndexConstituentDB" in __all__

    def test_exports_market_scan_run_db(self) -> None:
        """db/models/__init__.py must export MarketScanRunDB."""
        from stockvaluefinder.db.models import __all__

        assert "MarketScanRunDB" in __all__

    def test_exports_market_scan_candidate_db(self) -> None:
        """db/models/__init__.py must export MarketScanCandidateDB."""
        from stockvaluefinder.db.models import __all__

        assert "MarketScanCandidateDB" in __all__

    def test_exports_market_scan_rule_db(self) -> None:
        """db/models/__init__.py must export MarketScanRuleDB."""
        from stockvaluefinder.db.models import __all__

        assert "MarketScanRuleDB" in __all__
