"""
Instrumentation package.

Provides production-grade auto-instrumentation
for the ICYQuant platform, covering HTTP,
database, cache, messaging, and internal
components.

Submodules:
- base: Base Instrumentation class and registry
- manager: Async lifecycle manager
- registry: Global registry
- semantic: OpenTelemetry Semantic Conventions
- metrics: Instrumentation metrics
- fastapi: FastAPI HTTP server
- httpx: HTTPX HTTP client
- sqlalchemy: SQLAlchemy ORM
- asyncpg: AsyncPG PostgreSQL
- redis: Redis cache
- kafka: Kafka producer/consumer
- eventbus: ICYQuant EventBus
- scheduler: Task scheduler
- worker: Background worker
- grpc: gRPC client/server
"""

from .base import Instrumentation, InstrumentationRegistry
from .manager import InstrumentationManager
from .metrics import InstrumentationMetrics
from .registry import get_global_registry
from .fastapi import FastAPIInstrumentation
from .httpx import HTTPXInstrumentation
from .sqlalchemy import SQLAlchemyInstrumentation
from .asyncpg import AsyncPGInstrumentation
from .redis import RedisInstrumentation
from .kafka import KafkaInstrumentation
from .eventbus import EventBusInstrumentation
from .scheduler import SchedulerInstrumentation
from .worker import WorkerInstrumentation
from .grpc import gRPCInstrumentation

__all__ = [
    "Instrumentation",
    "InstrumentationRegistry",
    "InstrumentationManager",
    "InstrumentationMetrics",
    "get_global_registry",
    "FastAPIInstrumentation",
    "HTTPXInstrumentation",
    "SQLAlchemyInstrumentation",
    "AsyncPGInstrumentation",
    "RedisInstrumentation",
    "KafkaInstrumentation",
    "EventBusInstrumentation",
    "SchedulerInstrumentation",
    "WorkerInstrumentation",
    "gRPCInstrumentation",
]
