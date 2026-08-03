"""
Database exceptions.

Hierarchical exception types for precise
error handling across the database layer.
"""


class DatabaseError(Exception):
    """
    Base database exception.

    All database-related exceptions inherit
    from this class for unified catch blocks.
    """

    pass


class DatabaseConnectionError(DatabaseError):
    """
    Connection failed.

    Raised when the engine cannot establish
    or maintain a database connection.
    """

    pass


class DatabaseTransactionError(DatabaseError):
    """
    Transaction failed.

    Raised when a transaction (commit/rollback)
    encounters an error.
    """

    pass


class DatabaseTimeoutError(DatabaseError):
    """
    SQL timeout.

    Raised when a query or operation exceeds
    the configured time limit.
    """

    pass


class DatabaseHealthError(DatabaseError):
    """
    Database health check failed.

    Raised when the health check determines
    the database is unavailable or degraded.
    """

    pass