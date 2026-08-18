"""Redis-backed event bus - infrastructure adapter.

Implements the same publish/subscribe contract as the official
in-memory EventBus, but transports events over Redis pub/sub so
that independent engine containers can communicate.

Infrastructure only: no engine logic lives here.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Callable

import redis

from services.contracts.events import Event, EventType

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "icyquant:events:"


def _channel(event_type: EventType) -> str:
    return f"{CHANNEL_PREFIX}{event_type.value}"


class RedisEventBus:
    """Redis pub/sub implementation of the event bus contract."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        self._handlers: dict[str, list[Callable[[Event], None]]] = {}

    # -- publish side ---------------------------------------------------
    def publish(self, event: Event) -> None:
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "order_id": event.order_id,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
        self._redis.publish(_channel(event.event_type), json.dumps(payload))

    # -- subscribe side -------------------------------------------------
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        channel = _channel(event_type)
        self._handlers.setdefault(channel, []).append(handler)
        self._pubsub.subscribe(**{channel: self._dispatch})

    def _dispatch(self, message: dict) -> None:
        if message.get("type") != "message":
            return
        channel = message["channel"]
        raw = message["data"]
        try:
            data = json.loads(raw)
            event = Event(
                event_id=data["event_id"],
                event_type=EventType(data["event_type"]),
                order_id=data.get("order_id"),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                payload=data.get("payload") or {},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("dropping malformed event on %s: %s", channel, exc)
            return
        for handler in self._handlers.get(channel, []):
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001
                logger.error("event handler failed on %s: %s", channel, exc)

    def start_listening(self) -> None:
        """Start the background listener thread (call once per process)."""
        self._thread = self._pubsub.run_in_thread(sleep_time=0.05, daemon=True)

    def stop_listening(self) -> None:
        if hasattr(self, "_thread"):
            self._thread.stop()
