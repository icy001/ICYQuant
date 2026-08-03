"""
Instrumentation registry.

Re-exports the InstrumentationRegistry
from base.py for convenience and provides
a global registry instance.
"""

from __future__ import annotations

from .base import InstrumentationRegistry

__all__ = ["InstrumentationRegistry", "get_global_registry"]

_global_registry: InstrumentationRegistry | None = None


def get_global_registry() -> InstrumentationRegistry:
    """Get or create the global instrumentation registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = InstrumentationRegistry()
    return _global_registry
