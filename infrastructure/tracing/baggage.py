"""
Baggage context management.

Provides a key-value baggage context that
travels with trace context across service
boundaries, carrying business-relevant
metadata like user ID, account ID, and
strategy ID.

Baggage items:
- user.id: Authenticated user identifier
- account.id: Trading account identifier
- strategy.id: Active strategy identifier
- tenant: Tenant identifier
- region: Deployment region
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional


class BaggageManager:
    """
    Baggage context manager.

    Manages a key-value store that travels
    with trace context across service boundaries.
    Baggage items are propagated via headers
    alongside trace context.

    Usage:
        baggage = BaggageManager()

        # Set items
        baggage.put("user.id", "user-123")
        baggage.put("strategy.id", "strat-456")

        # Get items
        user_id = baggage.get("user.id")

        # Clear
        baggage.clear()
    """

    def __init__(
        self,
    ) -> None:
        """Initialize baggage manager."""

        self._baggage: ContextVar[Dict[str, str]] = ContextVar(
            "baggage", default={}
        )

    def put(
        self,
        key: str,
        value: str,
    ) -> None:
        """
        Set a baggage item.

        Args:
            key: Baggage key.
            value: Baggage value.
        """

        current = self._baggage.get()
        new_bag = dict(current)
        new_bag[key] = value
        self._baggage.set(new_bag)

    def get(
        self,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a baggage item.

        Args:
            key: Baggage key.
            default: Default value if not found.

        Returns:
            Baggage value or default.
        """

        return self._baggage.get().get(key, default)

    def get_all(
        self,
    ) -> Dict[str, str]:
        """
        Get all baggage items.

        Returns:
            Dictionary of all baggage items.
        """

        return dict(self._baggage.get())

    def delete(
        self,
        key: str,
    ) -> None:
        """
        Delete a baggage item.

        Args:
            key: Baggage key to delete.
        """

        current = self._baggage.get()
        if key in current:
            new_bag = dict(current)
            del new_bag[key]
            self._baggage.set(new_bag)

    def clear(
        self,
    ) -> None:
        """Clear all baggage items."""

        self._baggage.set({})

    def merge(
        self,
        items: Dict[str, str],
    ) -> None:
        """
        Merge items into baggage.

        Args:
            items: Dictionary of items to merge.
        """

        current = self._baggage.get()
        new_bag = dict(current)
        new_bag.update(items)
        self._baggage.set(new_bag)

    def is_empty(
        self,
    ) -> bool:
        """Check if baggage is empty."""

        return len(self._baggage.get()) == 0

    def __contains__(
        self,
        key: str,
    ) -> bool:
        """Check if key exists in baggage."""

        return key in self._baggage.get()

    def __len__(
        self,
    ) -> int:
        """Get number of baggage items."""

        return len(self._baggage.get())

    def to_header(
        self,
    ) -> str:
        """
        Serialize baggage to header string.

        Format: key1=value1,key2=value2

        Returns:
            Baggage header string.
        """

        items = self._baggage.get()
        return ",".join(f"{k}={v}" for k, v in items.items())

    @classmethod
    def from_header(
        cls,
        header: str,
    ) -> Dict[str, str]:
        """
        Parse baggage from header string.

        Args:
            header: Baggage header string.

        Returns:
            Dictionary of baggage items.
        """

        result: Dict[str, str] = {}
        if header:
            for item in header.split(","):
                if "=" in item:
                    key, value = item.split("=", 1)
                    result[key.strip()] = value.strip()
        return result
