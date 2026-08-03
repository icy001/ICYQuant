"""Unified exception hierarchy."""
from typing import Any, Optional

class ICYQuantError(Exception):
    """Base exception for all ICYQuant errors."""
    def __init__(self, message: str = "", error_code: int = 1000, details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ConfigurationError(ICYQuantError):
    def __init__(self, message: str = "Configuration error", **kwargs: Any):
        super().__init__(message=message, error_code=1001, **kwargs)

class InitializationError(ICYQuantError):
    def __init__(self, message: str = "Initialization error", **kwargs: Any):
        super().__init__(message=message, error_code=1002, **kwargs)

class DependencyError(ICYQuantError):
    def __init__(self, message: str = "Dependency error", **kwargs: Any):
        super().__init__(message=message, error_code=1003, **kwargs)

class ValidationError(ICYQuantError):
    def __init__(self, message: str = "Validation error", **kwargs: Any):
        super().__init__(message=message, error_code=2000, **kwargs)

class AuthenticationError(ICYQuantError):
    def __init__(self, message: str = "Authentication failed", **kwargs: Any):
        super().__init__(message=message, error_code=2001, **kwargs)

class AuthorizationError(ICYQuantError):
    def __init__(self, message: str = "Authorization failed", **kwargs: Any):
        super().__init__(message=message, error_code=2002, **kwargs)

class NotFoundError(ICYQuantError):
    def __init__(self, message: str = "Resource not found", **kwargs: Any):
        super().__init__(message=message, error_code=3000, **kwargs)

class ConflictError(ICYQuantError):
    def __init__(self, message: str = "Resource conflict", **kwargs: Any):
        super().__init__(message=message, error_code=3001, **kwargs)

class MarketDataError(ICYQuantError):
    def __init__(self, message: str = "Market data error", **kwargs: Any):
        super().__init__(message=message, error_code=4000, **kwargs)

class ExecutionError(ICYQuantError):
    def __init__(self, message: str = "Execution error", **kwargs: Any):
        super().__init__(message=message, error_code=4001, **kwargs)

class RiskViolationError(ICYQuantError):
    def __init__(self, message: str = "Risk limit violated", **kwargs: Any):
        super().__init__(message=message, error_code=4002, **kwargs)

class InfrastructureError(ICYQuantError):
    def __init__(self, message: str = "Infrastructure error", **kwargs: Any):
        super().__init__(message=message, error_code=5000, **kwargs)

class DatabaseError(InfrastructureError):
    def __init__(self, message: str = "Database error", **kwargs: Any):
        super().__init__(message=message, error_code=5001, **kwargs)

class RedisError(InfrastructureError):
    def __init__(self, message: str = "Redis error", **kwargs: Any):
        super().__init__(message=message, error_code=5002, **kwargs)

class KafkaError(InfrastructureError):
    def __init__(self, message: str = "Kafka error", **kwargs: Any):
        super().__init__(message=message, error_code=5003, **kwargs)
