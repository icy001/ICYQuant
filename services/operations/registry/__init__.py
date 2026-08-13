"""Service registry (Commit 27 Part 1.1)."""

from .registry import (
    RegisteredService,
    ServiceRegistry,
    validate_dependency,
)

__all__ = [
    "RegisteredService",
    "ServiceRegistry",
    "validate_dependency",
]
