"""Unit tests for configuration module."""

import dataclasses

from stockvaluefinder.config import ExternalDataConfig, get_arq_redis_settings


class TestExternalDataConfig:
    """Tests for ExternalDataConfig frozen dataclass and TTL fields."""

    def test_external_data_config_is_frozen(self) -> None:
        """ExternalDataConfig should be immutable (frozen=True)."""
        config = ExternalDataConfig()
        assert dataclasses.is_dataclass(config)

        # Verify frozen by attempting to set a field
        try:
            config.REDIS_URL = "redis://other:6379/0"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except dataclasses.FrozenInstanceError:
            pass  # Expected

    def test_default_redis_url(self) -> None:
        """REDIS_URL should default to localhost Redis on port 6380."""
        config = ExternalDataConfig()
        assert config.REDIS_URL == "redis://localhost:6380/0"

    def test_default_rate_cache_ttl(self) -> None:
        """RATE_CACHE_TTL should default to 3600 (1 hour)."""
        config = ExternalDataConfig()
        assert config.RATE_CACHE_TTL == 3600

    def test_default_shares_cache_ttl(self) -> None:
        """SHARES_CACHE_TTL should default to 86400 (24 hours)."""
        config = ExternalDataConfig()
        assert config.SHARES_CACHE_TTL == 86400

    def test_default_dividend_cache_ttl(self) -> None:
        """DIVIDEND_CACHE_TTL should default to 86400 (24 hours)."""
        config = ExternalDataConfig()
        assert config.DIVIDEND_CACHE_TTL == 86400

    def test_default_fcf_cache_ttl(self) -> None:
        """FCF_CACHE_TTL should default to 86400 (24 hours)."""
        config = ExternalDataConfig()
        assert config.FCF_CACHE_TTL == 86400

    def test_default_cache_key_version(self) -> None:
        """CACHE_KEY_VERSION should default to 'v1'."""
        config = ExternalDataConfig()
        assert config.CACHE_KEY_VERSION == "v1"

    def test_existing_fields_unchanged(self) -> None:
        """Pre-existing fields should retain their defaults."""
        config = ExternalDataConfig()
        assert config.ENABLE_AKSHARE is True
        assert config.PRICE_CACHE_TTL == 300
        assert config.FINANCIAL_DATA_CACHE_TTL == 86400
        assert config.MAX_RETRIES == 3
        assert config.RETRY_DELAY == 1.0

    def test_custom_values(self) -> None:
        """ExternalDataConfig should accept custom values."""
        config = ExternalDataConfig(
            REDIS_URL="redis://custom:6380/1",
            RATE_CACHE_TTL=7200,
            CACHE_KEY_VERSION="v2",
        )
        assert config.REDIS_URL == "redis://custom:6380/1"
        assert config.RATE_CACHE_TTL == 7200
        assert config.CACHE_KEY_VERSION == "v2"

    def test_get_arq_redis_settings_from_url(self) -> None:
        """get_arq_redis_settings should parse host/port/db from REDIS_URL."""
        settings = get_arq_redis_settings("redis://localhost:6380/0")
        assert settings.host == "localhost"
        assert settings.port == 6380
        assert settings.database == 0

    def test_all_ttl_fields_are_int(self) -> None:
        """All TTL fields should be integers."""
        config = ExternalDataConfig()
        ttl_fields = [
            config.PRICE_CACHE_TTL,
            config.FINANCIAL_DATA_CACHE_TTL,
            config.RATE_CACHE_TTL,
            config.SHARES_CACHE_TTL,
            config.DIVIDEND_CACHE_TTL,
            config.FCF_CACHE_TTL,
        ]
        for ttl in ttl_fields:
            assert isinstance(ttl, int), f"TTL {ttl} is not an int"
            assert ttl > 0, f"TTL {ttl} must be positive"
