"""Adapters for the Service Mesh.

Provides proxy adapter implementations: Internal (default),
Envoy (stub for production deployment), and Mock (for testing).
"""

from .internal import InternalProxyAdapter
from .envoy import EnvoyProxyAdapter
from .mock import MockProxyAdapter

__all__ = [
    "InternalProxyAdapter",
    "EnvoyProxyAdapter",
    "MockProxyAdapter",
]
