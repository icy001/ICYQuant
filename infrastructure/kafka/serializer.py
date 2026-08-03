"""
Kafka serializer.

Provides serialization/deserialization
for Kafka messages, supporting JSON and
extensible for other formats.
"""

from __future__ import annotations

import json
from typing import Any

from .exceptions import (
    KafkaSerializationError,
)


class JsonSerializer:
    """
    Default JSON serializer.

    Handles serialization of Python objects
    to JSON bytes for Kafka message payloads
    and deserialization back to Python objects.
    """

    @staticmethod
    def dumps(
        value: Any,
    ) -> bytes:
        """
        Serialize value to JSON bytes.

        Args:
            value: Any JSON-serializable object.

        Returns:
            Encoded bytes for Kafka message.

        Raises:
            KafkaSerializationError: On serialization failure.
        """

        try:
            return json.dumps(
                value,
                ensure_ascii=False,
            ).encode()

        except Exception as exc:
            raise KafkaSerializationError(
                str(exc)
            ) from exc

    @staticmethod
    def loads(
        value: bytes,
    ) -> Any:
        """
        Deserialize JSON bytes to Python object.

        Args:
            value: Raw bytes from Kafka message.

        Returns:
            Deserialized Python object.

        Raises:
            KafkaSerializationError: On deserialization failure.
        """

        try:
            return json.loads(
                value.decode()
            )

        except Exception as exc:
            raise KafkaSerializationError(
                str(exc)
            ) from exc
