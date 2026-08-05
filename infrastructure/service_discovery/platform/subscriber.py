"""Event subscriber manager for ICYQuant service discovery platform.

Provides ``DiscoverySubscriberManager`` for managing platform
event subscribers across business modules: OMS, Risk, Execution,
Gateway, Research, Strategy, and AI Platform.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext
from .publisher import DiscoveryEvent

logger = logging.getLogger(__name__)


class SubscriberInfo:
    """Information about a registered subscriber."""

    def __init__(
        self,
        name: str,
        module: str,
        callback: Callable,
        event_types: Optional[List[DiscoveryEvent]] = None,
    ) -> None:
        self.name = name
        self.module = module
        self.callback = callback
        self.event_types = event_types or []
        self.created_at = datetime.utcnow()
        self.call_count = 0
        self.last_called: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "event_types": [e.value for e in self.event_types],
            "call_count": self.call_count,
            "created_at": self.created_at.isoformat(),
            "last_called": (
                self.last_called.isoformat()
                if self.last_called
                else None
            ),
        }


class DiscoverySubscriberManager:
    """Manages platform event subscribers.

    Registers and dispatches events to business module
    subscribers such as OMS, Risk, Execution, Gateway,
    Research, Strategy, and AI Platform.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._subscribers: Dict[str, SubscriberInfo] = {}
        self._event_index: Dict[str, List[str]] = {}
        self._dispatch_count = 0
        self._subscribe_count = 0
        self._unsubscribe_count = 0

    def subscribe(
        self,
        name: str,
        module: str,
        callback: Callable,
        event_types: Optional[List[DiscoveryEvent]] = None,
    ) -> Dict[str, Any]:
        """Register a subscriber for platform events.

        Args:
            name: Subscriber name.
            module: Business module name.
            callback: Event handler callable.
            event_types: Event types to subscribe to.

        Returns:
            Subscribe result.
        """
        with self._lock:
            self._subscribe_count += 1
            self._subscribers[name] = SubscriberInfo(
                name, module, callback, event_types
            )

            if event_types:
                for et in event_types:
                    key = et.value
                    if key not in self._event_index:
                        self._event_index[key] = []
                    if name not in self._event_index[key]:
                        self._event_index[key].append(name)
            else:
                if "__all__" not in self._event_index:
                    self._event_index["__all__"] = []
                if name not in self._event_index["__all__"]:
                    self._event_index["__all__"].append(name)

        logger.info(
            "Subscriber '%s' registered for module '%s'.",
            name,
            module,
        )
        return {
            "success": True,
            "name": name,
            "module": module,
            "event_types": [
                e.value for e in (event_types or [])
            ],
        }

    def unsubscribe(self, name: str) -> Dict[str, Any]:
        """Remove a subscriber.

        Args:
            name: Subscriber to remove.

        Returns:
            Unsubscribe result.
        """
        with self._lock:
            self._unsubscribe_count += 1
            if name not in self._subscribers:
                return {
                    "success": False,
                    "error": f"Subscriber '{name}' not found",
                }
            del self._subscribers[name]
            for key in self._event_index:
                if name in self._event_index[key]:
                    self._event_index[key].remove(name)

        logger.info("Subscriber '%s' removed.", name)
        return {"success": True, "name": name}

    async def dispatch(
        self,
        event_type: DiscoveryEvent,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch an event to matching subscribers.

        Args:
            event_type: The event type.
            event_data: The event payload.

        Returns:
            Dispatch result.
        """
        with self._lock:
            self._dispatch_count += 1
            targets: List[str] = []
            key = event_type.value

            if key in self._event_index:
                targets.extend(self._event_index[key])
            if "__all__" in self._event_index:
                for name in self._event_index["__all__"]:
                    if name not in targets:
                        targets.append(name)

        dispatched = 0
        errors: List[str] = []

        for name in targets:
            sub = self._subscribers.get(name)
            if sub is None:
                continue
            try:
                coro = sub.callback(event_data or {})
                if asyncio.iscoroutine(coro):
                    await coro
                sub.call_count += 1
                sub.last_called = datetime.utcnow()
                dispatched += 1
            except Exception as exc:
                errors.append(f"{name}: {str(exc)}")
                logger.warning(
                    "Subscriber '%s' dispatch failed: %s",
                    name,
                    exc,
                )

        return {
            "success": True,
            "event_type": event_type.value,
            "dispatched": dispatched,
            "errors": errors,
        }

    def list_subscribers(
        self, module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            subs = list(self._subscribers.values())
        if module:
            subs = [s for s in subs if s.module == module]
        return [s.to_dict() for s in subs]

    def get_subscriber(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            sub = self._subscribers.get(name)
            if sub:
                return sub.to_dict()
        return None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "subscriber_count": len(self._subscribers),
                "subscribe_count": self._subscribe_count,
                "unsubscribe_count": self._unsubscribe_count,
                "dispatch_count": self._dispatch_count,
                "subscribers": [
                    s.to_dict()
                    for s in self._subscribers.values()
                ],
                "event_index": {
                    k: list(v)
                    for k, v in self._event_index.items()
                },
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoverySubscriberManager("
                f"subscribers={len(self._subscribers)}, "
                f"dispatches={self._dispatch_count})"
            )
