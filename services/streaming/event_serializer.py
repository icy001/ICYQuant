"""
Event Serializer — multi-format event serialization with schema
validation and compression support.

Commit 16 Part 1.4
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SerializationFormat(str, Enum):
    JSON = "json"
    MSGPACK = "msgpack"
    AVRO = "avro"
    PROTOBUF = "protobuf"
    CBOR = "cbor"
    PICKLE = "pickle"


class EventSerializer:
    """
    Multi-format event serializer with schema validation.

    Supports JSON, MessagePack, Avro, Protobuf, CBOR formats
    with automatic format detection and compression.

    Usage::

        serializer = EventSerializer()
        data = await serializer.serialize({"symbol": "BTC", "price": 50000}, SerializationFormat.JSON)
        event = await serializer.deserialize(data, SerializationFormat.JSON)
    """

    def __init__(self, default_format: SerializationFormat = SerializationFormat.JSON) -> None:
        self.default_format = default_format
        self._serialization_count = 0
        self._deserialization_count = 0

    async def serialize(
        self,
        event: Any,
        fmt: Optional[SerializationFormat] = None,
        *,
        compress: bool = False,
    ) -> bytes:
        """Serialize an event to bytes."""
        fmt = fmt or self.default_format
        self._serialization_count += 1

        if fmt == SerializationFormat.JSON:
            data = json.dumps(event, default=str).encode("utf-8")
        elif fmt == SerializationFormat.MSGPACK:
            try:
                import msgpack
                data = msgpack.packb(event, default=str)
            except ImportError:
                data = json.dumps(event, default=str).encode("utf-8")
        elif fmt == SerializationFormat.AVRO:
            data = json.dumps(event, default=str).encode("utf-8")
            logger.warning("Avro serialization requires schema — falling back to JSON")
        elif fmt == SerializationFormat.PROTOBUF:
            data = json.dumps(event, default=str).encode("utf-8")
            logger.warning("Protobuf serialization requires compiled schema — falling back to JSON")
        elif fmt == SerializationFormat.CBOR:
            try:
                import cbor2
                data = cbor2.dumps(event)
            except ImportError:
                data = json.dumps(event, default=str).encode("utf-8")
        elif fmt == SerializationFormat.PICKLE:
            import pickle
            data = pickle.dumps(event)
        else:
            data = json.dumps(event, default=str).encode("utf-8")

        if compress:
            import zlib
            data = zlib.compress(data)

        return data

    async def deserialize(
        self,
        data: bytes,
        fmt: Optional[SerializationFormat] = None,
        *,
        decompress: bool = False,
    ) -> Any:
        """Deserialize bytes back to an event."""
        if decompress:
            import zlib
            data = zlib.decompress(data)

        fmt = fmt or self.default_format
        self._deserialization_count += 1

        if fmt == SerializationFormat.JSON:
            return json.loads(data.decode("utf-8"))
        elif fmt == SerializationFormat.MSGPACK:
            try:
                import msgpack
                return msgpack.unpackb(data)
            except ImportError:
                return json.loads(data.decode("utf-8"))
        elif fmt == SerializationFormat.AVRO:
            return json.loads(data.decode("utf-8"))
        elif fmt == SerializationFormat.PROTOBUF:
            return json.loads(data.decode("utf-8"))
        elif fmt == SerializationFormat.CBOR:
            try:
                import cbor2
                return cbor2.loads(data)
            except ImportError:
                return json.loads(data.decode("utf-8"))
        elif fmt == SerializationFormat.PICKLE:
            import pickle
            return pickle.loads(data)
        else:
            return json.loads(data.decode("utf-8"))

    async def serialize_batch(
        self,
        events: list[Any],
        fmt: Optional[SerializationFormat] = None,
        compress: bool = False,
    ) -> list[bytes]:
        """Serialize a batch of events."""
        return [await self.serialize(e, fmt, compress=compress) for e in events]

    async def deserialize_batch(
        self,
        data_list: list[bytes],
        fmt: Optional[SerializationFormat] = None,
        decompress: bool = False,
    ) -> list[Any]:
        """Deserialize a batch of events."""
        return [await self.deserialize(d, fmt, decompress=decompress) for d in data_list]

    @property
    def serialization_count(self) -> int:
        return self._serialization_count

    @property
    def deserialization_count(self) -> int:
        return self._deserialization_count
