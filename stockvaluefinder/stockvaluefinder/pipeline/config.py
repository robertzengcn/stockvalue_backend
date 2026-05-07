"""Pipeline configuration settings.

This module contains the PipelineConfig frozen dataclass that controls
polling schedule, rate limits, retry policy, concurrency limits, and
watchlist scope for the financial report processing pipeline.

Follows the same frozen dataclass pattern as ValuationConfig, RiskConfig,
and YieldConfig in the main config.py module.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the financial report processing pipeline.

    Controls polling schedule, rate limits, retry policy, concurrency limits,
    stuck task reaper settings, watchlist scope, and season-aware polling.

    Attributes:
        max_retries: Maximum number of retry attempts for failed tasks.
        retry_delays: Delays in seconds between retry attempts.
            Must have at least max_retries entries.
        stuck_timeout_minutes: Minutes before a task in an active state
            is considered stuck and eligible for reaping.
        reaper_interval_minutes: How often the reaper cron checks for stuck tasks.
        max_concurrent_tasks: Maximum number of tasks processing concurrently.
        request_delay_seconds: Minimum delay between HTTP requests (rate limiting).
        job_timeout_seconds: Maximum seconds a single job can run before timeout.
        redis_db: Redis database number for arq job queue.
        default_watchlist: Default watchlist identifier (e.g., "CSI300").
        high_season_months: Months considered high reporting season (Jan-Apr default).
            Used for season-aware polling: daily in high season, weekly off-season.
        high_season_cron: Cron expression for high season polling (default daily 09:00).
        off_season_cron: Cron expression for off-season polling (default weekly Mon 09:00).
        sandbox_enabled: Whether to route calculations through CalculationSandboxService.
        sandbox_timeout: Maximum seconds a sandbox subprocess can run before timeout.

    Raises:
        ValueError: If any configuration value is invalid.
    """

    max_retries: int = 3
    retry_delays: tuple[float, ...] = (2.0, 8.0, 30.0)
    stuck_timeout_minutes: int = 30
    reaper_interval_minutes: int = 5
    max_concurrent_tasks: int = 5
    request_delay_seconds: float = 0.5
    job_timeout_seconds: int = 1800
    redis_db: int = 0
    default_watchlist: str = "CSI300"
    high_season_months: frozenset[int] = frozenset({1, 2, 3, 4})
    high_season_cron: str = "0 9 * * *"
    off_season_cron: str = "0 9 * * 1"
    sandbox_enabled: bool = False
    sandbox_timeout: int = 30

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")
        if self.stuck_timeout_minutes < 1:
            raise ValueError(
                f"stuck_timeout_minutes must be >= 1, got {self.stuck_timeout_minutes}"
            )
        if len(self.retry_delays) < self.max_retries:
            raise ValueError(
                f"retry_delays has {len(self.retry_delays)} entries, "
                f"but max_retries is {self.max_retries}"
            )
        if not self.high_season_months:
            raise ValueError("high_season_months must not be empty")
        if not all(1 <= m <= 12 for m in self.high_season_months):
            raise ValueError(
                f"high_season_months must be subset of {{1..12}}, "
                f"got {self.high_season_months}"
            )
        if not self.high_season_cron:
            raise ValueError("high_season_cron must not be empty")
        if not self.off_season_cron:
            raise ValueError("off_season_cron must not be empty")
        if self.sandbox_timeout < 1:
            raise ValueError(
                f"sandbox_timeout must be >= 1, got {self.sandbox_timeout}"
            )


__all__ = ["PipelineConfig"]
