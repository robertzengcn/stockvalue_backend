"""Unit tests for SSE endpoint (GET /api/v1/pipeline/events)."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSSEReplaysMissedEvents:
    """Test 6: SSE endpoint yields replayed events when Last-Event-ID header is present."""

    @pytest.mark.asyncio
    async def test_sse_replays_missed_events(self) -> None:
        """SSE yields replayed events with id and event type from Last-Event-ID."""
        from stockvaluefinder.api.pipeline_routes import sse_events

        replay_events = [
            {
                "id": "evt2",
                "type": "task_completed",
                "task_id": "task-1",
                "ticker": "600519.SH",
                "state": "done",
            }
        ]

        mock_pubsub = AsyncMock()

        async def mock_get_message(
            ignore_subscribe_messages: bool = True, timeout: float = 1.0
        ) -> None:
            return None

        mock_pubsub.get_message = mock_get_message
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers = {"Last-Event-ID": "evt1"}
        mock_request.is_disconnected = AsyncMock(return_value=False)

        with patch("stockvaluefinder.api.pipeline_routes.PipelineEventBus") as MockBus:
            mock_bus_instance = MockBus.return_value
            mock_bus_instance.replay_since = AsyncMock(return_value=replay_events)
            mock_bus_instance.subscribe = AsyncMock(return_value=mock_pubsub)

            # Get the response (EventSourceResponse)
            response = await sse_events(mock_request)

            # Access the generator directly
            collected: list[Any] = []
            async for event in response.body_iterator:
                collected.append(event)
                if len(collected) >= 2:
                    break

            # First event should be the replayed one
            assert collected[0]["id"] == "evt2"
            assert collected[0]["event"] == "task_completed"
            event_data = json.loads(collected[0]["data"])
            assert event_data["ticker"] == "600519.SH"


class TestSSEStreamsLiveEvents:
    """Test 7: SSE endpoint yields live events from Redis pub/sub."""

    @pytest.mark.asyncio
    async def test_sse_streams_live_events(self) -> None:
        """SSE yields live events received from Redis pub/sub."""
        from stockvaluefinder.api.pipeline_routes import sse_events

        live_event_data = json.dumps(
            {
                "id": "evt_live_1",
                "type": "task_created",
                "task_id": "task-2",
                "ticker": "000001.SZ",
                "state": "pending",
            }
        )

        call_count = 0

        async def mock_get_message(
            ignore_subscribe_messages: bool = True, timeout: float = 1.0
        ) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "message", "data": live_event_data.encode()}
            return None

        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = mock_get_message
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.is_disconnected = AsyncMock(return_value=False)

        with patch("stockvaluefinder.api.pipeline_routes.PipelineEventBus") as MockBus:
            mock_bus_instance = MockBus.return_value
            mock_bus_instance.replay_since = AsyncMock(return_value=[])
            mock_bus_instance.subscribe = AsyncMock(return_value=mock_pubsub)

            response = await sse_events(mock_request)

            collected: list[Any] = []
            async for event in response.body_iterator:
                collected.append(event)
                if len(collected) >= 2:
                    break

            # First event should be the live one
            assert collected[0]["id"] == "evt_live_1"
            assert collected[0]["event"] == "task_created"
            event_data = json.loads(collected[0]["data"])
            assert event_data["ticker"] == "000001.SZ"


class TestSSESendsPingKeepalive:
    """Test 8: SSE endpoint sends ping keep-alive when no messages arrive."""

    @pytest.mark.asyncio
    async def test_sse_sends_ping_keepalive(self) -> None:
        """SSE yields ping event when pubsub.get_message returns None (timeout)."""
        from stockvaluefinder.api.pipeline_routes import sse_events

        call_count = 0

        async def mock_get_message(
            ignore_subscribe_messages: bool = True, timeout: float = 1.0
        ) -> None:
            nonlocal call_count
            call_count += 1
            return None  # Always return None to trigger ping

        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = mock_get_message
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers = {}
        # Disconnect after 2 iterations so the generator stops
        mock_request.is_disconnected = AsyncMock(side_effect=[False, False, True])

        with patch("stockvaluefinder.api.pipeline_routes.PipelineEventBus") as MockBus:
            mock_bus_instance = MockBus.return_value
            mock_bus_instance.replay_since = AsyncMock(return_value=[])
            mock_bus_instance.subscribe = AsyncMock(return_value=mock_pubsub)

            response = await sse_events(mock_request)

            collected: list[Any] = []
            async for event in response.body_iterator:
                collected.append(event)

            # Should have ping events (empty data)
            ping_events = [e for e in collected if e.get("event") == "ping"]
            assert len(ping_events) >= 1
