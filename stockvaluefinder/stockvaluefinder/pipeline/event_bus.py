"""Redis-backed event bus for SSE pipeline notifications.

Publishes task lifecycle events (task_created, task_completed, task_failed)
via Redis pub/sub and persists last N events in a Redis LIST for reconnect
replay per D-01.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class PipelineEventBus:
    """Redis-backed event bus for pipeline task notifications.

    Publishes events via Redis pub/sub and persists last N events
    in a Redis list for reconnect replay per D-01.

    Attributes:
        CHANNEL: Redis pub/sub channel name.
        LOG_KEY: Redis LIST key for event log.
        MAX_EVENTS: Maximum events retained in log.
    """

    CHANNEL = "pipeline:events"
    LOG_KEY = "pipeline:event_log"
    MAX_EVENTS = 100

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(
        self,
        event_type: str,
        task_id: str,
        ticker: str,
        business_key: str,
        state: str,
    ) -> None:
        """Publish event to channel and append to log.

        Uses Redis pipeline for atomic RPUSH + LTRIM + PUBLISH.

        Args:
            event_type: One of task_created, task_completed, task_failed (per D-02).
            task_id: UUID of the pipeline task.
            ticker: Stock ticker.
            business_key: Task business key (ticker:fiscal_year:report_type).
            state: Current task state.
        """
        event_id = f"{int(time.time() * 1000)}:{uuid4().hex[:8]}"
        event = {
            "id": event_id,
            "type": event_type,
            "task_id": task_id,
            "ticker": ticker,
            "business_key": business_key,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        serialized = json.dumps(event)
        pipe = self._redis.pipeline()
        pipe.rpush(self.LOG_KEY, serialized)
        pipe.ltrim(self.LOG_KEY, -self.MAX_EVENTS, -1)
        pipe.publish(self.CHANNEL, serialized)
        await pipe.execute()

    async def replay_since(
        self, last_event_id: str, max_replay: int = 50
    ) -> list[dict[str, Any]]:
        """Replay events after the given event ID.

        Reads the most recent *max_replay* events from the event log and
        returns events after the matching ID. If ID not found, returns all
        replayed events (client disconnected too long).

        Args:
            last_event_id: The Last-Event-ID from the client.
            max_replay: Maximum number of events to scan (default 50).

        Returns:
            List of event dicts that arrived after the given ID.
        """
        all_events_raw: list[Any] = await self._redis.lrange(
            self.LOG_KEY, -max_replay, -1
        )  # type: ignore[misc]
        events = [json.loads(e) for e in all_events_raw]
        for i, evt in enumerate(events):
            if evt.get("id") == last_event_id:
                return events[i + 1 :]
        return events

    async def subscribe(self) -> Any:
        """Subscribe to the events channel.

        Returns:
            Redis pubsub object with active subscription.
        """
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.CHANNEL)
        return pubsub
