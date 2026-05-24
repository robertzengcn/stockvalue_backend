"""Tests that users-table Alembic migrations exist and define a compatible schema."""

from pathlib import Path


def _load_migration_module(filename: str):
    """Load an Alembic revision module by filename."""
    path = Path(__file__).resolve().parents[3] / "alembic" / "versions" / filename
    assert path.exists(), f"Expected migration file: {path}"
    source = path.read_text(encoding="utf-8")
    return path, source


class TestUsersMigrations:
    """Guard against missing or incompatible users-related schema migrations."""

    def test_users_table_migration_exists(self) -> None:
        """Migration 015 must create the users table required for registration."""
        path, source = _load_migration_module("015_users_table.py")
        assert path.name == "015_users_table.py"
        assert 'op.create_table(\n        "users"' in source
        assert "postgresql.UUID(as_uuid=True)" in source

    def test_users_soft_delete_migration_follows_users_table(self) -> None:
        """Migration 016 must extend users after 015."""
        _, source = _load_migration_module("016_users_soft_delete.py")
        assert 'revision: str = "016"' in source
        assert "down_revision" in source and '"015"' in source
        assert '"users"' in source
        assert '"deleted_at"' in source

    def test_user_fk_migrations_use_uuid_for_user_id(self) -> None:
        """FK columns referencing users.id must use UUID, not VARCHAR."""
        for filename in (
            "017_user_stock_access_table.py",
            "018_api_usage_records_table.py",
            "019_rate_limit_overrides_table.py",
        ):
            _, source = _load_migration_module(filename)
            assert "postgresql.UUID(as_uuid=True)" in source, (
                f"{filename} must use UUID for user_id FK to users.id"
            )
            assert (
                "sa.String()" not in source
                or 'sa.Column(\n            "user_id",\n            sa.String(),'
                not in source
            ), f"{filename} must not define user_id as VARCHAR"
