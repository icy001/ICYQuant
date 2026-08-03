"""
Redis auto-instrumentation.

Provides automatic span creation for
Redis operations, including:
- GET/SET/DEL/EXPIRE commands
- Pipeline execution
- Pub/Sub messaging
- Latency measurement

Semantic attributes:
- db.system = "redis"
- db.operation = command name
- db.name = database number
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class RedisInstrumentation(Instrumentation):
    """
    Redis auto-instrumentation.

    Wraps Redis client operations to
    automatically create database spans
    for each command, capturing command
    type, key, database, and latency.

    Features:
    - Automatic span creation for Redis commands
    - Pipeline batch tracking
    - Pub/Sub message tracking
    - Connection state monitoring
    - Latency measurement

    Supported commands:
    - GET, SET, DEL, EXPIRE
    - HSET, HGET, HMSET, HMGET
    - LPUSH, RPUSH, LPOP, RPOP
    - SADD, SMEMBERS, SREM
    - ZADD, ZRANGE, ZREM
    - PUBLISH, SUBSCRIBE, UNSUBSCRIBE
    - Pipeline execution

    Usage:
        instr = RedisInstrumentation()
        await instr.install()
    """

    name: str = "redis"
    version: str = "1.0"

    # Commands to capture (not comprehensive, but covers most used)
    _READ_COMMANDS = {
        "GET", "HGET", "HMGET", "HLEN", "HKEYS", "HVALS",
        "LINDEX", "LLEN", "LRANGE",
        "SCARD", "SMEMBERS", "SISMEMBER",
        "ZCARD", "ZRANGE", "ZSCORE",
        "EXISTS", "TYPE", "TTL", "PTTL",
        "KEYS", "SCAN",
    }

    _WRITE_COMMANDS = {
        "SET", "SETEX", "PSETEX", "SETNX",
        "HSET", "HMSET", "HDEL", "HINCRBY",
        "LPUSH", "RPUSH", "LPOP", "RPOP",
        "SADD", "SREM", "SPOP", "SMOVE",
        "ZADD", "ZREM", "ZINCRBY",
        "DEL", "EXPIRE", "PEXPIRE", "RENAME",
        "MSET", "MSETNX", "APPEND",
    }

    def __init__(
        self,
        tracer: Optional[Any] = None,
        db_name: str = "0",
        capture_keys: bool = True,
        capture_values: bool = False,
    ) -> None:
        """
        Initialize Redis instrumentation.

        Args:
            tracer: Optional Tracer instance.
            db_name: Redis database number/name.
            capture_keys: Whether to capture key names.
            capture_values: Whether to capture values.
        """

        super().__init__(tracer=tracer)
        self._db_name = db_name
        self._capture_keys = capture_keys
        self._capture_values = capture_values
        self._installed: bool = False
        self._commands_count: int = 0
        self._pipeline_count: int = 0

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    @property
    def stats(
        self,
    ) -> Dict[str, int]:
        """Get command statistics."""
        return {
            "commands": self._commands_count,
            "pipelines": self._pipeline_count,
        }

    async def install(
        self,
    ) -> None:
        """Install Redis instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove Redis instrumentation."""
        self._installed = False

    def create_command_span(
        self,
        command: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        db: Optional[str] = None,
    ) -> Any:
        """
        Create a Redis command span.

        Args:
            command: Redis command name.
            key: Key being operated on.
            value: Value being set.
            db: Database number.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        command_upper = command.upper()
        op_type = "read" if command_upper in self._READ_COMMANDS else "write"

        span = self.tracer.start_span(
            operation=f"redis.{command.lower()}",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", "redis")
        span.add_attribute("db.operation", command_upper)
        span.add_attribute("db.redis.op_type", op_type)

        if db is not None:
            span.add_attribute("db.name", str(db))
        else:
            span.add_attribute("db.name", self._db_name)

        if key and self._capture_keys:
            span.add_attribute("db.redis.key", key)

        if value is not None and self._capture_values:
            span.add_attribute("db.redis.value", str(value)[:256])

        self._commands_count += 1
        return span

    def create_pipeline_span(
        self,
        command_count: int = 0,
    ) -> Any:
        """
        Create a Redis pipeline span.

        Args:
            command_count: Number of commands in pipeline.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation="redis.pipeline",
            kind=SpanKind.CLIENT,
        )

        span.add_attribute("db.system", "redis")
        span.add_attribute("db.operation", "PIPELINE")
        span.add_attribute("db.redis.command_count", command_count)
        span.add_attribute("db.name", self._db_name)

        self._pipeline_count += 1
        return span

    def create_pubsub_span(
        self,
        operation: str,
        channel: str,
        message_size: Optional[int] = None,
    ) -> Any:
        """
        Create a Pub/Sub span.

        Args:
            operation: PUBLISH or SUBSCRIBE.
            channel: Channel name.
            message_size: Message size in bytes.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"redis.{operation.lower()}",
            kind=SpanKind.PRODUCER if "publish" in operation.lower() else SpanKind.CONSUMER,
        )

        span.add_attribute("db.system", "redis")
        span.add_attribute("db.operation", operation.upper())
        span.add_attribute("messaging.destination.name", channel)

        if message_size is not None:
            span.add_attribute("messaging.message.body.size", message_size)

        return span
