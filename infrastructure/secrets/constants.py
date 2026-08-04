"""
Secrets platform constants.

Defines enums and fixed values for
the secrets management platform,
including provider names, access levels,
and secret categories.
"""

from __future__ import annotations

from enum import Enum


class SecretsProvider(str, Enum):
    """Supported secrets provider types."""

    LOCAL = "local"
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    GOOGLE_SECRET_MANAGER = "google_secret_manager"
    ENVIRONMENT = "environment"


class SecretCategory(str, Enum):
    """Secret categories for classification."""

    CREDENTIAL = "credential"
    API_KEY = "api_key"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    ENCRYPTION_KEY = "encryption_key"
    PASSWORD = "password"
    CONNECTION_STRING = "connection_string"
    WEBHOOK = "webhook"
    OTHER = "other"


class AccessLevel(str, Enum):
    """Access permission levels."""

    NONE = 0
    READ = 1
    WRITE = 2
    ROTATE = 3
    DELETE = 4
    ADMIN = 5

    @property
    def can_read(self) -> bool:
        return self.value >= AccessLevel.READ.value

    @property
    def can_write(self) -> bool:
        return self.value >= AccessLevel.WRITE.value

    @property
    def can_rotate(self) -> bool:
        return self.value >= AccessLevel.ROTATE.value

    @property
    def can_delete(self) -> bool:
        return self.value >= AccessLevel.DELETE.value


class SecretStatus(str, Enum):
    """Secret lifecycle status."""

    ACTIVE = "active"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    DELETED = "deleted"


class AuditAction(str, Enum):
    """Audit log action types."""

    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    ROTATE = "rotate"
    CREATE = "create"
    ACCESS_DENIED = "access_denied"
    EXPIRED = "expired"
    REFRESH = "refresh"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"


class SecretFormat(str, Enum):
    """Secret value formats."""

    PLAINTEXT = "plaintext"
    JSON = "json"
    BASE64 = "base64"
    PEM = "pem"
    YAML = "yaml"
    TOML = "toml"


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Default values
DEFAULT_PROVIDER = SecretsProvider.LOCAL.value
DEFAULT_CACHE_TTL = 300
DEFAULT_CACHE_MAX_SIZE = 1000
DEFAULT_ROTATION_DAYS = 90
DEFAULT_NAMESPACE = "default"
DEFAULT_MAX_SECRET_SIZE = 65536
DEFAULT_RATE_LIMIT = 100

# Regex for secret reference resolution
SECRET_PATTERN = r"\$\{secret:([a-zA-Z0-9_/\-\.]+)\}"
SECRET_PREFIX = "${secret:"
SECRET_SUFFIX = "}"
