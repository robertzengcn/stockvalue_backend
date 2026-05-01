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
    stuck task reaper settings, and watchlist scope.

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


__all__ = ["PipelineConfig"]
