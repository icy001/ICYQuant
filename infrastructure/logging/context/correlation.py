"""
Correlation manager.

Manages correlation IDs for tracking
business operations across the entire
trade lifecycle:

    Request → Trace → Strategy → Signal → Order
    → Execution → Trade → Position → Ledger

All operations within a single business
flow share the same correlation_id,
enabling end-to-end log correlation.
"""

from __future__ import annotations

import uuid
from typing import Optional

from .manager import ContextManager
from .models import LogContext


class CorrelationManager:
    """
    Business correlation manager.

    Provides methods for creating, getting,
    and managing correlation IDs that
    span the entire trade lifecycle.

    Usage:
        # Start a new correlation
        corr_id = CorrelationManager.start()

        # Get current correlation
        cid = CorrelationManager.get_id()

        # Set specific correlation
        CorrelationManager.set_id("order-12345")

        # Clear correlation
        CorrelationManager.clear()
    """

    @staticmethod
    def start(
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Start a new correlation.

        Generates a new correlation ID if
        not provided, and sets it in the
        current context.

        Args:
            correlation_id: Optional explicit correlation ID.

        Returns:
            The correlation ID.
        """

        cid = correlation_id or str(uuid.uuid4())
        ContextManager.update(correlation_id=cid)
        return cid

    @staticmethod
    def get_id() -> Optional[str]:
        """
        Get the current correlation ID.

        Returns:
            Current correlation ID or None.
        """

        return ContextManager.get().correlation_id

    @staticmethod
    def set_id(
        correlation_id: str,
    ) -> None:
        """
        Set the correlation ID.

        Args:
            correlation_id: Correlation ID to set.
        """

        ContextManager.update(correlation_id=correlation_id)

    @staticmethod
    def clear() -> None:
        """Clear the correlation ID."""

        ContextManager.update(correlation_id=None)

    @staticmethod
    def is_set() -> bool:
        """Check if correlation ID is set."""

        return ContextManager.get().correlation_id is not None

    @staticmethod
    def propagate(
        headers: dict,
    ) -> dict:
        """
        Propagate correlation ID to headers.

        Args:
            headers: Headers dict to inject into.

        Returns:
            Updated headers dict.
        """

        cid = CorrelationManager.get_id()
        if cid:
            headers["X-Correlation-ID"] = cid
        return headers

    @staticmethod
    def extract(
        headers: dict,
    ) -> Optional[str]:
        """
        Extract correlation ID from headers.

        Args:
            headers: Headers dict to extract from.

        Returns:
            Correlation ID or None.
        """

        lower = {k.lower(): v for k, v in headers.items()}
        return lower.get("x-correlation-id")
