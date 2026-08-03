"""
Monitoring collectors.

Provides infrastructure-level metrics collectors
for Database, Redis, Kafka, Storage, Application,
and Business modules. Each collector integrates
with the corresponding infrastructure metrics
class to produce standardized MetricPoint objects.

All collectors extend BaseCollector for consistent
naming, labeling, and error handling.

Usage:
    from infrastructure.monitoring.collectors import (
        DatabaseCollector,
        RedisCollector,
        KafkaCollector,
        StorageCollector,
        ApplicationCollector,
        BusinessCollector,
    )

    db_collector = DatabaseCollector(database_engine)
    registry.add_collector("database", db_collector)
"""

from .application import ApplicationCollector
from .business import BusinessCollector
from .database import DatabaseCollector
from .kafka import KafkaCollector
from .redis import RedisCollector
from .storage import StorageCollector

__all__ = [
    "DatabaseCollector",
    "RedisCollector",
    "KafkaCollector",
    "StorageCollector",
    "ApplicationCollector",
    "BusinessCollector",
]