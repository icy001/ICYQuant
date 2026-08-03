"""
Kafka exceptions.

Hierarchical exception types for precise
error handling across the Kafka layer.
"""


class KafkaError(Exception):
    """
    Base Kafka exception.

    All Kafka-related exceptions inherit
    from this class for unified catch blocks.
    """

    pass


class KafkaConnectionError(KafkaError):
    """
    Kafka connection error.

    Raised when the client cannot establish
    or maintain a Kafka connection.
    """

    pass


class KafkaPublishError(KafkaError):
    """
    Kafka publish error.

    Raised when publishing a message
    to Kafka fails.
    """

    pass


class KafkaConsumeError(KafkaError):
    """
    Kafka consume error.

    Raised when consuming messages
    from Kafka fails.
    """

    pass


class KafkaSerializationError(KafkaError):
    """
    Kafka serialization error.

    Raised when value serialization or
    deserialization encounters an error.
    """

    pass
