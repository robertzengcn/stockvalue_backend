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


class TestPipelineConfigSeasonAwarePolling:
    """Test PipelineConfig season-aware polling fields (Phase 6, D-07, D-08, D-09)."""

    def test_default_high_season_months(self) -> None:
        """D-07: Default high season months are Jan-Apr (1,2,3,4)."""
        config = PipelineConfig()
        assert config.high_season_months == frozenset({1, 2, 3, 4})

    def test_default_high_season_cron(self) -> None:
        """D-08: Default high season cron is daily at 09:00."""
        config = PipelineConfig()
        assert config.high_season_cron == "0 9 * * *"

    def test_default_off_season_cron(self) -> None:
        """D-08: Default off-season cron is weekly Monday at 09:00."""
        config = PipelineConfig()
        assert config.off_season_cron == "0 9 * * 1"

    def test_custom_high_season_months(self) -> None:
        """D-07: Accepts custom frozenset of months."""
        config = PipelineConfig(high_season_months=frozenset({1, 2, 3, 4, 7, 8}))
        assert config.high_season_months == frozenset({1, 2, 3, 4, 7, 8})

    def test_custom_cron_strings(self) -> None:
        """D-09: Accepts custom cron expressions."""
        config = PipelineConfig(
            high_season_cron="0 10 * * *",
            off_season_cron="0 10 * * 1",
        )
        assert config.high_season_cron == "0 10 * * *"
        assert config.off_season_cron == "0 10 * * 1"

    def test_rejects_high_season_months_out_of_range(self) -> None:
        """D-07: Rejects months outside 1-12."""
        with pytest.raises(ValueError, match="high_season_months"):
            PipelineConfig(high_season_months=frozenset({0, 1, 2}))

    def test_rejects_high_season_months_above_12(self) -> None:
        """D-07: Rejects months above 12."""
        with pytest.raises(ValueError, match="high_season_months"):
            PipelineConfig(high_season_months=frozenset({1, 13}))

    def test_rejects_empty_high_season_months(self) -> None:
        """D-07: Rejects empty high season months."""
        with pytest.raises(ValueError, match="high_season_months"):
            PipelineConfig(high_season_months=frozenset())

    def test_rejects_empty_high_season_cron(self) -> None:
        """D-09: Rejects empty high season cron string."""
        with pytest.raises(ValueError, match="high_season_cron"):
            PipelineConfig(high_season_cron="")

    def test_rejects_empty_off_season_cron(self) -> None:
        """D-09: Rejects empty off season cron string."""
        with pytest.raises(ValueError, match="off_season_cron"):
            PipelineConfig(off_season_cron="")

    def test_frozen_high_season_months(self) -> None:
        """Frozen: Cannot mutate high_season_months."""
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.high_season_months = frozenset({5, 6})  # type: ignore[misc]

    def test_frozen_high_season_cron(self) -> None:
        """Frozen: Cannot mutate high_season_cron."""
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.high_season_cron = "0 8 * * *"  # type: ignore[misc]

    def test_frozen_off_season_cron(self) -> None:
        """Frozen: Cannot mutate off_season_cron."""
        config = PipelineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.off_season_cron = "0 8 * * 1"  # type: ignore[misc]

    def test_existing_fields_still_validate_after_new_fields(self) -> None:
        """Existing PipelineConfig fields (max_retries, retry_delays, etc.) still work."""
        config = PipelineConfig(
            max_retries=2,
            retry_delays=(1.0, 5.0),
            stuck_timeout_minutes=60,
        )
        assert config.max_retries == 2
        assert config.high_season_months == frozenset({1, 2, 3, 4})
        assert config.high_season_cron == "0 9 * * *"
