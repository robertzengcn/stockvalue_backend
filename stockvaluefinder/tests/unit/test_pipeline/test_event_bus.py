"""Unit tests for PipelineEventBus (Redis pub/sub + LIST event bus)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock redis.asyncio.Redis instance."""
    return AsyncMock()


@pytest.fixture
def mock_pipeline(mock_redis: AsyncMock) -> MagicMock:
    """Create a mock Redis pipeline object."""
    pipeline = MagicMock()
    # Redis pipeline methods return self for chaining (synchronous style)
    pipeline.rpush = MagicMock(return_value=pipeline)
    pipeline.ltrim = MagicMock(return_value=pipeline)
    pipeline.publish = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock()
    # pipeline() must return the pipeline synchronously (not as coroutine)
    mock_redis.pipeline = MagicMock(return_value=pipeline)
    return pipeline


class TestPublishCallsRedisPipeline:
    """Test 1: PipelineEventBus.publish() calls RPUSH, LTRIM, PUBLISH on Redis pipeline."""

    @pytest.mark.asyncio
    async def test_publish_calls_redis_pipeline(
        self, mock_redis: AsyncMock, mock_pipeline: MagicMock
    ) -> None:
        """publish() calls RPUSH, LTRIM, PUBLISH via Redis pipeline."""
        from stockvaluefinder.pipeline.event_bus import PipelineEventBus

        bus = PipelineEventBus(mock_redis)
        await bus.publish(
            event_type="task_created",
            task_id="abc-123",
            ticker="600519.SH",
            business_key="600519.SH:2023:annual",
            state="pending",
        )

        # Verify pipeline was created and execute() called
        mock_redis.pipeline.assert_called_once()
        mock_pipeline.execute.assert_awaited_once()

        # Verify RPUSH called with LOG_KEY
        mock_pipeline.rpush.assert_called_once()
        rpush_args = mock_pipeline.rpush.call_args
        assert rpush_args[0][0] == PipelineEventBus.LOG_KEY

        # Verify LTRIM called with (-MAX_EVENTS, -1)
        mock_pipeline.ltrim.assert_called_once_with(
            PipelineEventBus.LOG_KEY,
            -PipelineEventBus.MAX_EVENTS,
            -1,
        )

        # Verify PUBLISH called with CHANNEL
        mock_pipeline.publish.assert_called_once()
        publish_args = mock_pipeline.publish.call_args
        assert publish_args[0][0] == PipelineEventBus.CHANNEL


class TestPublishEventStructure:
    """Test 2: PipelineEventBus.publish() generates correct event structure."""

    @pytest.mark.asyncio
    async def test_publish_event_structure(
        self, mock_redis: AsyncMock, mock_pipeline: MagicMock
    ) -> None:
        """publish() generates event with id, type, timestamp, task_id, ticker, business_key, state."""
        from stockvaluefinder.pipeline.event_bus import PipelineEventBus

        bus = PipelineEventBus(mock_redis)
        await bus.publish(
            event_type="task_created",
            task_id="abc-123",
            ticker="600519.SH",
            business_key="600519.SH:2023:annual",
            state="pending",
        )

        # Extract the serialized event from RPUSH call
        rpush_args = mock_pipeline.rpush.call_args[0]
        serialized = rpush_args[1]
        event = json.loads(serialized)

        assert "id" in event
        assert event["type"] == "task_created"
        assert event["task_id"] == "abc-123"
        assert event["ticker"] == "600519.SH"
        assert event["business_key"] == "600519.SH:2023:annual"
        assert event["state"] == "pending"
        assert "timestamp" in event

        # Verify event ID format: {timestamp_ms}:{random_hex}
        assert ":" in event["id"]


class TestReplaySinceReturnsEventsAfterId:
    """Test 3: PipelineEventBus.replay_since() returns events after given Last-Event-ID."""

    @pytest.mark.asyncio
    async def test_replay_since_returns_events_after_id(
        self, mock_redis: AsyncMock
    ) -> None:
        """replay_since('evt1') returns events after the matching ID."""
        from stockvaluefinder.pipeline.event_bus import PipelineEventBus

        events_in_log = [
            json.dumps({"id": "evt1", "type": "task_created"}),
            json.dumps({"id": "evt2", "type": "task_completed"}),
            json.dumps({"id": "evt3", "type": "task_failed"}),
        ]
        mock_redis.lrange.return_value = events_in_log

        bus = PipelineEventBus(mock_redis)
        result = await bus.replay_since("evt1")

        assert len(result) == 2
        assert result[0]["id"] == "evt2"
        assert result[1]["id"] == "evt3"


class TestReplaySinceReturnsAllIfIdNotFound:
    """Test 4: PipelineEventBus.replay_since() returns all events if Last-Event-ID not found."""

    @pytest.mark.asyncio
    async def test_replay_since_returns_all_if_id_not_found(
        self, mock_redis: AsyncMock
    ) -> None:
        """replay_since('nonexistent') returns all events when ID not found."""
        from stockvaluefinder.pipeline.event_bus import PipelineEventBus

        events_in_log = [
            json.dumps({"id": "evt1", "type": "task_created"}),
            json.dumps({"id": "evt2", "type": "task_completed"}),
        ]
        mock_redis.lrange.return_value = events_in_log

        bus = PipelineEventBus(mock_redis)
        result = await bus.replay_since("nonexistent")

        assert len(result) == 2
        assert result[0]["id"] == "evt1"
        assert result[1]["id"] == "evt2"


class TestSubscribeReturnsPubsub:
    """Test 5: PipelineEventBus.subscribe() returns a pubsub object subscribed to channel."""

    @pytest.mark.asyncio
    async def test_subscribe_returns_pubsub(self, mock_redis: AsyncMock) -> None:
        """subscribe() returns pubsub with channel subscribed."""
        from stockvaluefinder.pipeline.event_bus import PipelineEventBus

        mock_pubsub = AsyncMock()
        # pubsub() must return synchronously (not as coroutine)
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        bus = PipelineEventBus(mock_redis)
        result = await bus.subscribe()

        mock_redis.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_awaited_once_with(PipelineEventBus.CHANNEL)
        assert result is mock_pubsub
