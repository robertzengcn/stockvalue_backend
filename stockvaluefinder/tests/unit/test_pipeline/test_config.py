"""Tests for PipelineConfig frozen dataclass with validation."""

import dataclasses

import pytest

from stockvaluefinder.pipeline.config import PipelineConfig


class TestPipelineConfigDefaults:
    """Test PipelineConfig creates with default values."""

    def test_default_max_retries(self) -> None:
        config = PipelineConfig()
        assert config.max_retries == 3

    def test_default_retry_delays(self) -> None:
        config = PipelineConfig()
        assert config.retry_delays == (2.0, 8.0, 30.0)

    def test_default_stuck_timeout_minutes(self) -> None:
        config = PipelineConfig()
        assert config.stuck_timeout_minutes == 30

    def test_default_reaper_interval_minutes(self) -> None:
        config = PipelineConfig()
        assert config.reaper_interval_minutes == 5

    def test_default_max_concurrent_tasks(self) -> None:
        config = PipelineConfig()
        assert config.max_concurrent_tasks == 5

    def test_default_request_delay_seconds(self) -> None:
        config = PipelineConfig()
        assert config.request_delay_seconds == 0.5

    def test_default_job_timeout_seconds(self) -> None:
        config = PipelineConfig()
        assert config.job_timeout_seconds == 1800

    def test_default_redis_db(self) -> None:
        config = PipelineConfig()
        assert config.redis_db == 0

    def test_default_watchlist(self) -> None:
        config = PipelineConfig()
        assert config.default_watchlist == "CSI300"


class TestPipelineConfigValidation:
    """Test PipelineConfig rejects invalid values."""

    def test_negative_max_retries_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            PipelineConfig(max_retries=-1)

    def test_zero_stuck_timeout_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="stuck_timeout_minutes"):
            PipelineConfig(stuck_timeout_minutes=0)

    def test_negative_stuck_timeout_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="stuck_timeout_minutes"):
            PipelineConfig(stuck_timeout_minutes=-5)

    def test_retry_delays_shorter_than_max_retries_raises_value_error(self) -> None:
        with pytest.raises(
            ValueError, match="retry_delays has 1 entries, but max_retries is 3"
        ):
            PipelineConfig(retry_delays=(2.0,), max_retries=3)

    def test_zero_max_retries_is_valid(self) -> None:
        """Zero max_retries means no retries, which is valid."""
        config = PipelineConfig(max_retries=0)
        assert config.max_retries == 0

    def test_retry_delays_matching_max_retries_is_valid(self) -> None:
        """retry_delays length equals max_retries is valid."""
        config = PipelineConfig(retry_delays=(1.0, 2.0, 3.0), max_retries=3)
        assert config.retry_delays == (1.0, 2.0, 3.0)

    def test_retry_delays_longer_than_max_retries_is_valid(self) -> None:
        """Extra retry delays are fine, only used up to max_retries."""
        config = PipelineConfig(retry_delays=(1.0, 2.0, 3.0, 4.0), max_retries=3)
        assert config.max_retries == 3


class TestPipelineConfigFrozen:
    """Test PipelineConfig is immutable (frozen=True)."""

    def test_frozen_max_retries(self) -> None:
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.max_retries = 5  # type: ignore[misc]

    def test_frozen_stuck_timeout_minutes(self) -> None:
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.stuck_timeout_minutes = 60  # type: ignore[misc]

    def test_frozen_default_watchlist(self) -> None:
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.default_watchlist = "CSI500"  # type: ignore[misc]
