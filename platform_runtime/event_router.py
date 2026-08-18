"""
ICYQuant Platform - Event Router

Central event bus with pub/sub, filtering, prioritization, and broadcasting.
Connects modules through an event-driven architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Event:
    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.event_id,
            "topic": self.topic,
            "payload": self.payload,
            "source": self.source,
            "priority": self.priority.name,
            "timestamp": self.timestamp.isoformat(),
            "correlationId": self.correlation_id,
        }


@dataclass
class EventSubscription:
    subscriber_id: str
    topic: str
    handler: Callable[[Event], None]
    filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    min_priority: EventPriority = EventPriority.LOW
    active: bool = True

    def matches(self, event: Event) -> bool:
        if not self.active:
            return False
        if event.priority > self.min_priority:
            return False
        if self.filter_fn and not self.filter_fn(event.payload):
            return False
        return True


class EventRouter:
    """
    Central event bus for the platform.

    Supports topic-based pub/sub with filtering, prioritization,
    and both unicast and broadcast delivery modes.
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[EventSubscription]] = {}
        self._wildcard_subs: List[EventSubscription] = []
        self._event_log: List[Event] = []
        self._max_log_size = 10000
        self._dead_letter: List[Event] = []
        self._stats = {"published": 0, "delivered": 0, "failed": 0}

    def subscribe(
        self,
        subscriber_id: str,
        topic: str,
        handler: Callable[[Event], None],
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        min_priority: EventPriority = EventPriority.LOW,
    ) -> str:
        sub_id = str(uuid.uuid4())
        sub = EventSubscription(
            subscriber_id=subscriber_id,
            topic=topic,
            handler=handler,
            filter_fn=filter_fn,
            min_priority=min_priority,
        )

        if topic == "*":
            self._wildcard_subs.append(sub)
        else:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
            self._subscriptions[topic].append(sub)

        logger.debug(f"Subscription added: {subscriber_id} -> {topic}")
        return sub_id

    def unsubscribe(self, subscriber_id: str, topic: Optional[str] = None):
        if topic:
            subs = self._subscriptions.get(topic, [])
            self._subscriptions[topic] = [
                s for s in subs if s.subscriber_id != subscriber_id
            ]
        else:
            for topic, subs in self._subscriptions.items():
                self._subscriptions[topic] = [
                    s for s in subs if s.subscriber_id != subscriber_id
                ]
            self._wildcard_subs = [
                s for s in self._wildcard_subs if s.subscriber_id != subscriber_id
            ]

    def publish(
        self,
        topic: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "",
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str = "",
    ) -> Event:
        event = Event(
            topic=topic,
            payload=payload or {},
            source=source,
            priority=priority,
            correlation_id=correlation_id,
        )
        self._publish_event(event)
        return event

    def _publish_event(self, event: Event):
        self._stats["published"] += 1
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        recipients = []
        topic_subs = self._subscriptions.get(event.topic, [])
        wildcard_subs = self._wildcard_subs

        for sub in topic_subs + wildcard_subs:
            if sub.matches(event):
                recipients.append(sub)

        recipients.sort(key=lambda s: s.min_priority)

        for sub in recipients:
            try:
                sub.handler(event)
                self._stats["delivered"] += 1
            except Exception as e:
                self._stats["failed"] += 1
                self._dead_letter.append(event)
                logger.error(
                    f"Event delivery failed: {event.topic} -> {sub.subscriber_id}: {e}"
                )

        logger.debug(
            f"Event published: {event.topic} to {len(recipients)} recipients"
        )

    def broadcast(
        self,
        topic: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "",
        priority: EventPriority = EventPriority.LOW,
    ) -> Event:
        return self.publish(topic, payload, source, priority)

    def get_event_log(
        self,
        topic: Optional[str] = None,
        limit: int = 50,
    ) -> List[Event]:
        events = self._event_log
        if topic:
            events = [e for e in events if e.topic == topic]
        return events[-limit:]

    def get_dead_letter(self, limit: int = 50) -> List[Event]:
        return self._dead_letter[-limit:]

    def clear_dead_letter(self):
        self._dead_letter.clear()

    def get_topics(self) -> List[str]:
        return list(self._subscriptions.keys())

    def get_subscribers(self, topic: str) -> List[str]:
        subs = self._subscriptions.get(topic, [])
        return [s.subscriber_id for s in subs]

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def get_status(self) -> Dict:
        return {
            "totalSubscriptions": sum(len(s) for s in self._subscriptions.values()),
            "wildcardSubscriptions": len(self._wildcard_subs),
            "topics": len(self._subscriptions),
            "eventLogSize": len(self._event_log),
            "deadLetterSize": len(self._dead_letter),
            "stats": self._stats,
        }

    def to_dict(self) -> Dict:
        return self.get_status()
