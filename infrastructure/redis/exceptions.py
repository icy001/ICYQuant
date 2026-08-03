"""
Redis exceptions.

Hierarchical exception types for precise
error handling across the Redis layer.
"""


class RedisError(Exception):
    """
    Base Redis exception.

    All Redis-related exceptions inherit
    from this class for unified catch blocks.
    """

    pass


class RedisConnectionError(RedisError):
    """
    Redis connection failed.

    Raised when the client cannot establish
    or maintain a Redis connection.
    """

    pass


class RedisTimeoutError(RedisError):
    """
    Redis operation timeout.

    Raised when a Redis command exceeds
    the configured time limit.
    """

    pass


class RedisSerializationError(RedisError):
    """
    Redis serialization failed.

    Raised when value serialization or
    deserialization encounters an error.
    """

    pass


class DistributedLockError(RedisError):
    """
    Distributed lock error.

    Raised when acquiring or releasing
    a distributed lock encounters an issue.
    """

    pass


class CacheOperationError(RedisError):
    """
    Cache operation failed.

    Raised when a cache operation (get, set,
    delete, etc.) encounters an error.
    """

    pass