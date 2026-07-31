"""Unified configuration management using Pydantic Settings.

Provides type-safe, validated configuration for the ICYQuant platform.
Nested models (ApplicationSettings, ServerSettings, SecuritySettings,
DatabaseSettings, RedisSettings, KafkaSettings, BrokerSettings) group
related settings into domain-scoped objects, while flat property
accessors are preserved for backward compatibility.
"""
from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_APP_NAME: str = "ICYQuant"
DEFAULT_VERSION: str = "0.4.0-alpha2"
DEFAULT_TIMEZONE: str = "UTC"


# ============================================================================
# Base Configuration Model
# ============================================================================


class BaseConfig(BaseModel):
    """Shared base class for all nested configuration models.

    Provides consistent Pydantic v2 model configuration:
    - ``extra="ignore"``: unknown environment variables are silently ignored.
    - ``populate_by_name=True``: allows population via field names.
    - ``validate_assignment=True``: re-validates on attribute assignment.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
    )


# ============================================================================
# Enumerations
# ============================================================================


class Environment(str, Enum):
    """Runtime environment enumeration.

    ``__missing__`` allows string values such as ``"test"`` or ``"PRODUCTION"``
    to be resolved to the canonical enum member regardless of casing.
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def _missing_(cls, value: Any) -> Optional["Environment"]:  # type: ignore[override]
        if isinstance(value, str):
            normalized = value.strip().lower()
            # Common alias mapping
            alias = {"test": cls.TESTING, "prod": cls.PRODUCTION}
            if normalized in alias:
                return alias[normalized]
            for member in cls:
                if member.value == normalized:
                    return member
        return None

    @classmethod
    def from_value(cls, value: str) -> "Environment":
        """Create an Environment from a string value (with alias support)."""
        return cls(value)


class LogLevel(str, Enum):
    """Logging severity level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def _missing_(cls, value: Any) -> Optional["LogLevel"]:  # type: ignore[override]
        if isinstance(value, str):
            normalized = value.strip().upper()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class BrokerType(str, Enum):
    """Supported broker adapter types."""

    PAPER = "paper"
    IBKR = "ibkr"
    FIX = "fix"
    REST = "rest"


class LoggingFormat(str, Enum):
    """Supported logging output formats."""

    TEXT = "text"
    JSON = "json"


# ============================================================================
# Application Settings
# ============================================================================


class ApplicationSettings(BaseConfig):
    """Application metadata and runtime parameters."""

    name: str = Field(
        default=DEFAULT_APP_NAME,
        description="Application display name",
    )
    version: str = Field(
        default=DEFAULT_VERSION,
        description="Application version",
    )
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Runtime environment",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Server host address",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port",
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode",
    )
    timezone: str = Field(
        default=DEFAULT_TIMEZONE,
        description="Application timezone",
    )

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        return self.environment == Environment.TESTING


# ============================================================================
# Server Settings
# ============================================================================


class ServerSettings(BaseConfig):
    """API server, logging, and observability settings."""

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log level",
    )
    log_format: str = Field(
        default="json",
        description="Log output format",
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Log file path (if None, logs to stdout only)",
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics endpoint",
    )
    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Metrics server port",
    )
    tracing_enabled: bool = Field(
        default=True,
        description="Enable distributed tracing",
    )
    tracing_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OpenTelemetry OTLP exporter endpoint",
    )


# ============================================================================
# Security Settings
# ============================================================================


class SecuritySettings(BaseConfig):
    """Security and credential settings."""

    jwt_secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        min_length=8,
        description="JWT signing secret key",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        ge=1,
        description="JWT access token TTL in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="JWT refresh token TTL in days",
    )
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production-please"),
        min_length=8,
        description="Application-level encryption key",
    )
    secret_rotation_days: int = Field(
        default=90,
        ge=1,
        description="Secret key rotation interval in days",
    )


# ============================================================================
# Database Settings
# ============================================================================


class DatabaseSettings(BaseConfig):
    """
    Relational database configuration.

    Default production target:
        PostgreSQL

    Used by:
        - Ledger
        - Portfolio
        - OMS
        - Risk Engine
        - Research Metadata
    """

    host: str = Field(
        default="localhost",
        description="Database host",
    )
    port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Database port",
    )
    username: str = Field(
        default="icyquant",
        description="Database username",
    )
    password: str = Field(
        default="icyquant",
        description="Database password",
    )
    database: str = Field(
        default="icyquant",
        description="Database name",
    )
    pool_size: int = Field(
        default=20,
        ge=1,
        description="SQLAlchemy connection pool size",
    )
    max_overflow: int = Field(
        default=10,
        ge=0,
        description="SQLAlchemy max overflow connections",
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="SQLAlchemy pool checkout timeout in seconds",
    )
    echo_sql: bool = Field(
        default=False,
        description="Enable SQL debug logging",
    )

    @property
    def url(self) -> str:
        """
        Build SQLAlchemy async database URL.

        Returns:
            PostgreSQL connection URL with asyncpg driver.
        """
        return (
            "postgresql+asyncpg://"
            f"{self.username}:"
            f"{self.password}@"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.database}"
        )


# ============================================================================
# Redis Settings
# ============================================================================


class RedisSettings(BaseConfig):
    """
    Redis infrastructure configuration.

    Used by:
        - Cache
        - Session
        - Rate Limit
        - Distributed Lock
        - Event State
    """

    host: str = Field(
        default="localhost",
        description="Redis host",
    )
    port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis port",
    )
    database: int = Field(
        default=0,
        ge=0,
        description="Redis database index",
    )
    password: Optional[str] = Field(
        default=None,
        description="Redis password",
    )
    ssl: bool = Field(
        default=False,
        description="Enable Redis TLS",
    )
    max_connections: int = Field(
        default=50,
        ge=1,
        description="Redis connection pool size",
    )
    timeout: int = Field(
        default=5,
        ge=1,
        description="Redis connection timeout in seconds",
    )

    @property
    def url(self) -> str:
        """
        Build Redis connection URL.
        """
        scheme = "rediss" if self.ssl else "redis"
        auth = ""
        if self.password:
            auth = f":{self.password}@"
        return (
            f"{scheme}://"
            f"{auth}"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.database}"
        )


# ============================================================================
# Kafka Settings
# ============================================================================


class KafkaSettings(BaseConfig):
    """
    Kafka event streaming configuration.

    Used by:
        - Market Data Pipeline
        - Event Bus
        - OMS
        - EMS
        - Risk Events
    """

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers",
    )
    client_id: str = Field(
        default="icyquant",
        description="Kafka client identifier",
    )
    group_id: str = Field(
        default="icyquant-worker",
        description="Kafka consumer group",
    )
    security_protocol: str = Field(
        default="PLAINTEXT",
        description="Kafka security protocol",
    )
    enable_auto_commit: bool = Field(
        default=False,
        description="Kafka consumer auto commit",
    )
    max_poll_records: int = Field(
        default=500,
        ge=1,
        description="Maximum records per poll",
    )


# ============================================================================
# Broker Settings
# ============================================================================


class BrokerSettings(BaseConfig):
    """
    Trading broker connection settings.

    Used by:
        - Execution Engine
        - OMS
        - EMS
    """

    enabled: bool = Field(
        default=False,
        description="Enable broker connection",
    )
    broker_type: BrokerType = Field(
        default=BrokerType.PAPER,
        description="Broker adapter type",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Broker API key",
    )
    api_secret: Optional[str] = Field(
        default=None,
        description="Broker API secret",
    )
    endpoint: Optional[str] = Field(
        default=None,
        description="Broker API endpoint",
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        description="Broker request timeout",
    )

    @property
    def is_configured(self) -> bool:
        """Return True when credentials and endpoint are set."""
        return bool(self.api_key and self.api_secret and self.endpoint)


# ============================================================================
# JWT Settings
# ============================================================================


class JWTSettings(BaseConfig):
    """
    JSON Web Token authentication configuration.

    Used by:
        - API Authentication
        - User Session
        - RBAC Authorization
    """

    enabled: bool = Field(
        default=True,
        description="Enable JWT authentication",
    )
    secret_key: SecretStr = Field(
        default=SecretStr("change-this-secret"),
        min_length=16,
        description="JWT signing secret",
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT algorithm",
    )
    issuer: str = Field(
        default="icyquant",
        description="JWT issuer",
    )
    audience: str = Field(
        default="icyquant-api",
        description="JWT audience",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Access token lifetime",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Refresh token lifetime",
    )


# ============================================================================
# Logging Settings
# ============================================================================


class LoggingSettings(BaseConfig):
    """
    Application logging configuration.

    Designed for:
        - Local Development
        - Production Containers
        - ELK / Loki Pipeline
    """

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Global logging level",
    )
    format: LoggingFormat = Field(
        default=LoggingFormat.JSON,
        description="Log output format",
    )
    enable_console: bool = Field(
        default=True,
        description="Enable console output",
    )
    enable_file: bool = Field(
        default=False,
        description="Enable file logging",
    )
    file_path: str = Field(
        default="logs/icyquant.log",
        description="Log file path",
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        description="Maximum log file size",
    )
    backup_count: int = Field(
        default=10,
        ge=0,
        description="Rotating log backup count",
    )


# ============================================================================
# Metrics Settings
# ============================================================================


class MetricsSettings(BaseConfig):
    """
    Metrics collection configuration.

    Used by:
        - Prometheus
        - Grafana
        - AlertManager
    """

    enabled: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    endpoint: str = Field(
        default="/metrics",
        description="Metrics HTTP endpoint",
    )
    port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Metrics server port",
    )
    namespace: str = Field(
        default="icyquant",
        description="Prometheus metric namespace",
    )


# ============================================================================
# Tracing Settings
# ============================================================================


class TracingSettings(BaseConfig):
    """
    Distributed tracing configuration.

    Compatible with:
        - OpenTelemetry
        - Jaeger
        - Tempo
    """

    enabled: bool = Field(
        default=False,
        description="Enable distributed tracing",
    )
    service_name: str = Field(
        default="icyquant",
        description="Tracing service name",
    )
    exporter: str = Field(
        default="otlp",
        description="Tracing exporter",
    )
    endpoint: Optional[str] = Field(
        default=None,
        description="Tracing collector endpoint",
    )
    sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate",
    )


# ============================================================================
# Feature Flags
# ============================================================================


class FeatureFlags(BaseConfig):
    """
    Runtime feature switches.

    Allows safe rollout of new capabilities.
    """

    enable_ai_strategy: bool = Field(
        default=False,
        description="Enable AI strategy engine",
    )
    enable_live_trading: bool = Field(
        default=False,
        description="Enable live trading",
    )
    enable_paper_trading: bool = Field(
        default=True,
        description="Enable paper trading",
    )
    enable_event_replay: bool = Field(
        default=True,
        description="Enable event replay engine",
    )
    enable_risk_guard: bool = Field(
        default=True,
        description="Enable risk protection",
    )
    enable_feature_store: bool = Field(
        default=False,
        description="Enable ML feature store",
    )


# ============================================================================
# CORS Settings
# ============================================================================


class CORSSettings(BaseConfig):
    """
    Cross-Origin Resource Sharing settings.

    Used by:

        Web Dashboard
        Mobile Client
        External API Consumer
    """

    enabled: bool = Field(
        default=True,
        description="Enable CORS",
    )
    allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
        ],
        description="Allowed frontend origins",
    )
    allow_methods: list[str] = Field(
        default_factory=lambda: [
            "GET",
            "POST",
            "PUT",
            "DELETE",
        ],
        description="Allowed HTTP methods",
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: [
            "Authorization",
            "Content-Type",
        ],
        description="Allowed headers",
    )
    allow_credentials: bool = Field(
        default=True,
        description="Allow credentials",
    )


# ============================================================================
# API Settings
# ============================================================================


class APISettings(BaseConfig):
    """
    API gateway configuration.

    Controls:

        REST API
        OpenAPI
        Request Limits
        Versioning
    """

    prefix: str = Field(
        default="/api/v1",
        description="API route prefix",
    )
    title: str = Field(
        default="ICYQuant API",
        description="API title",
    )
    description: str = Field(
        default=(
            "Institutional quantitative trading platform API"
        ),
        description="API description",
    )
    docs_enabled: bool = Field(
        default=True,
        description="Enable OpenAPI docs",
    )
    openapi_url: str = Field(
        default="/openapi.json",
        description="OpenAPI schema path",
    )
    max_request_size_mb: int = Field(
        default=10,
        ge=1,
        description="Maximum request payload size",
    )
    request_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="API request timeout",
    )


# ============================================================================
# Rate Limit Settings
# ============================================================================


class RateLimitSettings(BaseConfig):
    """
    API rate limiting configuration.

    Protects:

        Trading API
        Authentication API
        Public API
    """

    enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    requests_per_minute: int = Field(
        default=120,
        ge=1,
        description="Default user request limit",
    )
    burst_size: int = Field(
        default=20,
        ge=1,
        description="Burst request capacity",
    )
    trading_requests_per_second: int = Field(
        default=10,
        ge=1,
        description="Trading endpoint limit",
    )
    strategy_requests_per_minute: int = Field(
        default=60,
        ge=1,
        description="Strategy API limit",
    )


# ============================================================================
# Cache Settings
# ============================================================================


class CacheBackend(str, Enum):
    """
    Cache backend options.
    """

    MEMORY = "memory"

    REDIS = "redis"


class CacheSettings(BaseConfig):
    """
    Application cache configuration.

    Used by:

        Market Data
        Feature Store
        API Cache
    """

    enabled: bool = Field(
        default=True,
        description="Enable caching",
    )
    backend: CacheBackend = Field(
        default=CacheBackend.REDIS,
        description="Cache backend",
    )
    default_ttl_seconds: int = Field(
        default=300,
        ge=1,
        description="Default cache TTL",
    )
    market_data_ttl_seconds: int = Field(
        default=5,
        ge=1,
        description="Market data cache TTL",
    )


# ============================================================================
# Research Settings
# ============================================================================


class ResearchSettings(BaseConfig):
    """
    Quantitative research configuration.

    Used by:

        Backtest Engine
        Factor Research
        Alpha Research
    """

    workspace_path: str = Field(
        default="workspace/research",
        description="Research workspace path",
    )
    dataset_path: str = Field(
        default="data/datasets",
        description="Dataset storage path",
    )
    max_parallel_jobs: int = Field(
        default=4,
        ge=1,
        description="Maximum parallel research jobs",
    )
    enable_notebook: bool = Field(
        default=True,
        description="Enable notebook integration",
    )


# ============================================================================
# AI Runtime Settings
# ============================================================================


class AIRuntimeSettings(BaseConfig):
    """
    AI inference runtime configuration.

    Used by:

        Alpha Model
        Signal Model
        Strategy AI
    """

    enabled: bool = Field(
        default=False,
        description="Enable AI runtime",
    )
    provider: str = Field(
        default="local",
        description="AI runtime provider",
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Model artifact path",
    )
    device: str = Field(
        default="cpu",
        description="Inference device",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        description="Inference batch size",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Inference timeout",
    )


# ============================================================================
# Deployment Settings
# ============================================================================


class DeploymentMode(str, Enum):
    """
    Deployment runtime mode.
    """

    LOCAL = "local"

    DOCKER = "docker"

    KUBERNETES = "kubernetes"

    CLOUD = "cloud"


class DeploymentSettings(BaseConfig):
    """
    Deployment configuration.

    Used by:

        Docker
        Kubernetes
        Cloud Runtime
    """

    mode: DeploymentMode = Field(
        default=DeploymentMode.LOCAL,
        description="Deployment mode",
    )

    region: str = Field(
        default="cn-east",
        description="Deployment region",
    )

    instance_id: str = Field(
        default="icyquant-node-001",
        description="Runtime instance identifier",
    )

    graceful_shutdown_seconds: int = Field(
        default=30,
        ge=1,
        description="Shutdown timeout",
    )

    enable_auto_restart: bool = Field(
        default=True,
        description="Enable automatic restart",
    )


# ============================================================================
# Kubernetes Settings
# ============================================================================


class KubernetesSettings(BaseConfig):
    """
    Kubernetes runtime configuration.

    Used by:

        Helm Deployment
        Health Probe
        Autoscaling
    """

    enabled: bool = Field(
        default=False,
        description="Enable Kubernetes mode",
    )

    namespace: str = Field(
        default="icyquant",
        description="Kubernetes namespace",
    )

    service_name: str = Field(
        default="icyquant-api",
        description="Kubernetes service name",
    )

    pod_name: Optional[str] = Field(
        default=None,
        description="Current pod name",
    )

    enable_probe: bool = Field(
        default=True,
        description="Enable health probes",
    )


# ============================================================================
# Storage Settings
# ============================================================================


class StorageBackend(str, Enum):
    """
    Storage backend options.
    """

    LOCAL = "local"

    S3 = "s3"

    MINIO = "minio"


class StorageSettings(BaseConfig):
    """
    File and object storage configuration.

    Used by:

        Dataset Store
        Model Artifact
        Report Archive
    """

    backend: StorageBackend = Field(
        default=StorageBackend.LOCAL,
        description="Storage backend",
    )

    base_path: str = Field(
        default="data",
        description="Storage root path",
    )

    bucket: Optional[str] = Field(
        default=None,
        description="Object storage bucket",
    )

    endpoint: Optional[str] = Field(
        default=None,
        description="Object storage endpoint",
    )

    access_key: Optional[str] = Field(
        default=None,
        description="Storage access key",
    )

    secret_key: Optional[str] = Field(
        default=None,
        description="Storage secret key",
    )


# ============================================================================
# Compliance Settings
# ============================================================================


class ComplianceSettings(BaseConfig):
    """
    Compliance and audit configuration.

    Used by:

        Audit Trail
        Ledger
        Trading Records
    """

    enable_audit_log: bool = Field(
        default=True,
        description="Enable audit logging",
    )

    retain_days: int = Field(
        default=2555,
        ge=1,
        description="Audit retention days",
    )

    immutable_records: bool = Field(
        default=True,
        description="Enable immutable records",
    )

    enable_trade_reconciliation: bool = Field(
        default=True,
        description="Enable reconciliation checks",
    )


# ============================================================================
# Environment Validation
# ============================================================================


class EnvironmentValidator(BaseConfig):
    """
    Environment-specific validation rules.

    Each environment has a different set of required settings.
    The Settings.validate_environment() method checks these
    rules before the application starts.
    """

    required_env_vars: list[str] = Field(
        default_factory=list,
        description="Required environment variable names",
    )
    required_configs: list[str] = Field(
        default_factory=list,
        description="Required nested config paths (e.g., 'database.url')",
    )
    warn_on_defaults: bool = Field(
        default=True,
        description="Warn when default values are used in non-dev environments",
    )


def validate_environment_settings(
    settings: "Settings",
) -> tuple[list[str], list[str]]:
    """
    Validate environment-specific configuration requirements.

    Returns a tuple of (violations, warnings).
    """
    violations: list[str] = []
    warnings: list[str] = []

    env = settings.APP_ENV

    # Development: minimal checks
    if env == "development":
        if settings.APP_DEBUG is False:
            warnings.append(
                "Development environment with debug mode disabled"
            )

    # Staging: moderate checks
    elif env == "staging":
        if settings.APP_DEBUG:
            violations.append(
                "STAGING: debug mode must be disabled — set APP_DEBUG=false"
            )
        if not settings.TRACING_ENABLED:
            warnings.append(
                "STAGING: tracing is recommended but not enabled"
            )

    # Production: strict checks
    elif env == "production":
        try:
            settings.validate_production()
        except ValueError as e:
            violations.append(str(e))

        if not settings.METRICS_ENABLED:
            violations.append(
                "PRODUCTION: metrics must be enabled"
            )

        if settings.CACHE_BACKEND == "memory":
            violations.append(
                "PRODUCTION: cache backend should not be 'memory'"
            )

    return violations, warnings


# ============================================================================
# Configuration Validators
# ============================================================================


def validate_production_settings(
    settings: "Settings",
) -> None:
    """
    Validate production safety rules.

    Raises:
        ValueError:
            When unsafe configuration detected.
    """

    if (
        settings.application.environment
        == Environment.PRODUCTION
    ):

        if (
            settings.security.secret_key
            in ("change-me", "change-me-in-production-please")
        ):
            raise ValueError(
                "Production requires secure secret key"
            )

        if (
            settings.application.debug
        ):
            raise ValueError(
                "Debug mode cannot enabled in production"
            )

        if (
            not settings.compliance.enable_audit_log
        ):
            raise ValueError(
                "Production requires audit logging"
            )


# ============================================================================
# Legacy Environment Variable Mapping
# ============================================================================

# Legacy flat env-key -> nested_path mapping.
# Used by Settings._remap_legacy_env() to back-port legacy keys into
# nested models when they are NOT also provided via new-style paths.
_LEGACY_KEY_MAP: dict[str, str] = {
    # Application
    "APP_NAME": "application.name",
    "APP_VERSION": "application.version",
    "APP_ENV": "application.environment",
    "APP_HOST": "application.host",
    "APP_PORT": "application.port",
    "APP_DEBUG": "application.debug",
    # Server / logging
    "LOG_LEVEL": "logging.level",
    "LOG_FORMAT": "logging.format",
    "LOG_FILE": "logging.file_path",
    # Database
    "DATABASE_URL": "database.url",
    "DATABASE_POOL_SIZE": "database.pool_size",
    "DATABASE_MAX_OVERFLOW": "database.max_overflow",
    "DATABASE_POOL_TIMEOUT": "database.pool_timeout",
    # Redis
    "REDIS_URL": "redis.url",
    "REDIS_POOL_SIZE": "redis.max_connections",
    "REDIS_TIMEOUT": "redis.timeout",
    # Kafka
    "KAFKA_BOOTSTRAP_SERVERS": "kafka.bootstrap_servers",
    "KAFKA_GROUP_ID": "kafka.group_id",
    "KAFKA_AUTO_OFFSET_RESET": "kafka.enable_auto_commit",
    # Security / JWT
    "JWT_SECRET_KEY": "jwt.secret_key",
    "JWT_ALGORITHM": "jwt.algorithm",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "jwt.access_token_expire_minutes",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "jwt.refresh_token_expire_days",
    "SECRET_KEY": "security.secret_key",
    "SECRET_ROTATION_DAYS": "security.secret_rotation_days",
    # Broker
    "BROKER_NAME": "broker.broker_type",
    "BROKER_API_KEY": "broker.api_key",
    "BROKER_API_SECRET": "broker.api_secret",
    "BROKER_BASE_URL": "broker.endpoint",
    # Observability
    "METRICS_ENABLED": "metrics.enabled",
    "METRICS_PORT": "metrics.port",
    "TRACING_ENABLED": "tracing.enabled",
    "TRACING_EXPORTER_OTLP_ENDPOINT": "tracing.endpoint",
    # Feature flags
    "ENABLE_AI_STRATEGY": "features.enable_ai_strategy",
    "ENABLE_LIVE_TRADING": "features.enable_live_trading",
    "ENABLE_PAPER_TRADING": "features.enable_paper_trading",
    "ENABLE_EVENT_REPLAY": "features.enable_event_replay",
    "ENABLE_RISK_GUARD": "features.enable_risk_guard",
    "ENABLE_FEATURE_STORE": "features.enable_feature_store",
    # CORS
    "CORS_ENABLED": "cors.enabled",
    "CORS_ALLOW_ORIGINS": "cors.allow_origins",
    # API
    "API_PREFIX": "api.prefix",
    "API_DOCS_ENABLED": "api.docs_enabled",
    # Rate limit
    "RATE_LIMIT_ENABLED": "rate_limit.enabled",
    "RATE_LIMIT_RPM": "rate_limit.requests_per_minute",
    "RATE_LIMIT_BURST": "rate_limit.burst_size",
    # Cache
    "CACHE_ENABLED": "cache.enabled",
    "CACHE_BACKEND": "cache.backend",
    "CACHE_DEFAULT_TTL": "cache.default_ttl_seconds",
    # Research
    "RESEARCH_WORKSPACE": "research.workspace_path",
    "RESEARCH_MAX_JOBS": "research.max_parallel_jobs",
    # AI Runtime
    "AI_RUNTIME_ENABLED": "ai.enabled",
    "AI_PROVIDER": "ai.provider",
    "AI_MODEL_PATH": "ai.model_path",
    "AI_DEVICE": "ai.device",
    "AI_TIMEOUT": "ai.timeout_seconds",
    # Deployment
    "DEPLOYMENT_MODE": "deployment.mode",
    "DEPLOYMENT_REGION": "deployment.region",
    "INSTANCE_ID": "deployment.instance_id",
    # Kubernetes
    "K8S_NAMESPACE": "kubernetes.namespace",
    "K8S_SERVICE_NAME": "kubernetes.service_name",
    # Storage
    "STORAGE_BACKEND": "storage.backend",
    "STORAGE_BASE_PATH": "storage.base_path",
    # Compliance
    "AUDIT_LOG_ENABLED": "compliance.enable_audit_log",
    "AUDIT_RETAIN_DAYS": "compliance.retain_days",
    "IMMUTABLE_RECORDS": "compliance.immutable_records",
}


def _parse_database_url(url: str) -> dict[str, Any]:
    """Parse a legacy DATABASE_URL string into component fields.

    Supports formats:
        postgresql://user:pass@host:port/dbname
        postgresql+asyncpg://user:pass@host:port/dbname
    """
    parsed = urlparse(url)
    result: dict[str, Any] = {}

    if parsed.hostname:
        result["host"] = parsed.hostname
    if parsed.port:
        result["port"] = parsed.port
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    if parsed.path and parsed.path.startswith("/"):
        result["database"] = parsed.path[1:]

    return result


def _parse_redis_url(url: str) -> dict[str, Any]:
    """Parse a legacy REDIS_URL string into component fields.

    Supports formats:
        redis://host:port/db
        rediss://:pass@host:port/db
    """
    parsed = urlparse(url)
    result: dict[str, Any] = {}

    if parsed.hostname:
        result["host"] = parsed.hostname
    if parsed.port:
        result["port"] = parsed.port
    if parsed.path and parsed.path.startswith("/"):
        try:
            result["database"] = int(parsed.path[1:])
        except ValueError:
            result["database"] = 0
    if parsed.username == "" and parsed.password:
        result["password"] = parsed.password
    elif parsed.username:
        result["password"] = parsed.username

    scheme = parsed.scheme
    if scheme == "rediss":
        result["ssl"] = True

    return result


# ============================================================================
# Root Settings
# ============================================================================


class Settings(BaseSettings):
    """
    Global ICYQuant configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    api: APISettings = Field(default_factory=APISettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    ai: AIRuntimeSettings = Field(default_factory=AIRuntimeSettings)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    compliance: ComplianceSettings = Field(default_factory=ComplianceSettings)

    # ------ Legacy env-var remapper ------

    @model_validator(mode="before")
    @classmethod
    def _remap_legacy_env(cls, data: Any) -> Any:
        """Remap legacy flat env keys into nested model structure.

        Handles three input scenarios:
        1. Settings constructed with explicit kwargs (tests, internal).
        2. Settings constructed with env vars picked up by pydantic-settings.
        3. Settings constructed from a ``.env`` file.
        """
        if not isinstance(data, dict):
            return data

        remapped: dict[str, Any] = dict(data)

        # Special handling for URL-based legacy keys that need parsing
        for url_key, parser in [
            ("DATABASE_URL", _parse_database_url),
            ("REDIS_URL", _parse_redis_url),
        ]:
            url_value = remapped.get(url_key) or os.environ.get(url_key)
            if url_value:
                parsed = parser(url_value)
                # Place parsed components into the nested dict
                nested_path = _LEGACY_KEY_MAP.get(url_key, "")
                parent_key = nested_path.split(".")[0] if "." in nested_path else ""
                if parent_key:
                    target = remapped.setdefault(parent_key, {})
                    if isinstance(target, dict):
                        for comp_field, comp_val in parsed.items():
                            if comp_field not in target:
                                target[comp_field] = comp_val

        # Generic legacy key remapping for non-URL keys
        for flat_key, nested_path in _LEGACY_KEY_MAP.items():
            if flat_key in ("DATABASE_URL", "REDIS_URL"):
                continue  # Already handled above

            if flat_key in remapped:
                # Explicit value provided: place into nested structure
                parts = nested_path.split(".")
                target = remapped.setdefault(parts[0], {})
                if isinstance(target, dict) and parts[-1] not in target:
                    target[parts[-1]] = remapped[flat_key]
                continue

            # Fall back to os.environ for runtime resolution
            env_val = os.environ.get(flat_key)
            if env_val is None:
                continue

            parts = nested_path.split(".")
            target = remapped.setdefault(parts[0], {})
            if isinstance(target, dict) and parts[-1] not in target:
                target[parts[-1]] = env_val

        return remapped

    # ------ Backward-compatible flat property accessors ------

    # Application
    @property
    def APP_NAME(self) -> str:  # noqa: N802
        return self.application.name

    @property
    def APP_VERSION(self) -> str:  # noqa: N802
        return self.application.version

    @property
    def APP_ENV(self) -> str:  # noqa: N802
        return self.application.environment.value

    @property
    def APP_HOST(self) -> str:  # noqa: N802
        return self.application.host

    @property
    def APP_PORT(self) -> int:  # noqa: N802
        return self.application.port

    @property
    def APP_DEBUG(self) -> bool:  # noqa: N802
        return self.application.debug

    @property
    def is_production(self) -> bool:
        return self.application.is_production

    @property
    def is_development(self) -> bool:
        return self.application.is_development

    @property
    def is_test(self) -> bool:
        return self.application.is_test

    # Server / logging
    @property
    def LOG_LEVEL(self) -> str:  # noqa: N802
        return self.logging.level.value

    @property
    def LOG_FORMAT(self) -> str:  # noqa: N802
        return self.logging.format.value

    @property
    def LOG_FILE(self) -> Optional[str]:  # noqa: N802
        return self.logging.file_path if self.logging.enable_file else None

    # Database
    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return self.database.url

    @property
    def DATABASE_POOL_SIZE(self) -> int:  # noqa: N802
        return self.database.pool_size

    @property
    def DATABASE_MAX_OVERFLOW(self) -> int:  # noqa: N802
        return self.database.max_overflow

    @property
    def DATABASE_POOL_TIMEOUT(self) -> int:  # noqa: N802
        return self.database.pool_timeout

    # Redis
    @property
    def REDIS_URL(self) -> str:  # noqa: N802
        return self.redis.url

    @property
    def REDIS_POOL_SIZE(self) -> int:  # noqa: N802
        return self.redis.max_connections

    @property
    def REDIS_TIMEOUT(self) -> int:  # noqa: N802
        return self.redis.timeout

    # Kafka
    @property
    def KAFKA_BOOTSTRAP_SERVERS(self) -> str:  # noqa: N802
        return self.kafka.bootstrap_servers

    @property
    def KAFKA_GROUP_ID(self) -> str:  # noqa: N802
        return self.kafka.group_id

    @property
    def KAFKA_AUTO_OFFSET_RESET(self) -> str:  # noqa: N802
        return str(self.kafka.enable_auto_commit).lower()

    # Security / JWT
    @property
    def JWT_SECRET_KEY(self) -> str:  # noqa: N802
        return self.jwt.secret_key.get_secret_value()

    @property
    def JWT_ALGORITHM(self) -> str:  # noqa: N802
        return self.jwt.algorithm

    @property
    def JWT_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:  # noqa: N802
        return self.jwt.access_token_expire_minutes

    @property
    def JWT_REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:  # noqa: N802
        return self.jwt.refresh_token_expire_days

    @property
    def SECRET_KEY(self) -> str:  # noqa: N802
        return self.security.secret_key.get_secret_value()

    @property
    def SECRET_ROTATION_DAYS(self) -> int:  # noqa: N802
        return self.security.secret_rotation_days

    # Broker
    @property
    def BROKER_NAME(self) -> str:  # noqa: N802
        return self.broker.broker_type.value

    @property
    def BROKER_API_KEY(self) -> str:  # noqa: N802
        return self.broker.api_key or ""

    @property
    def BROKER_API_SECRET(self) -> str:  # noqa: N802
        return self.broker.api_secret or ""

    @property
    def BROKER_BASE_URL(self) -> str:  # noqa: N802
        return self.broker.endpoint or ""

    # Observability
    @property
    def METRICS_ENABLED(self) -> bool:  # noqa: N802
        return self.metrics.enabled

    @property
    def METRICS_PORT(self) -> int:  # noqa: N802
        return self.metrics.port

    @property
    def TRACING_ENABLED(self) -> bool:  # noqa: N802
        return self.tracing.enabled

    @property
    def TRACING_EXPORTER_OTLP_ENDPOINT(self) -> str:  # noqa: N802
        return self.tracing.endpoint or ""

    # Feature flags
    @property
    def ENABLE_AI_STRATEGY(self) -> bool:  # noqa: N802
        return self.features.enable_ai_strategy

    @property
    def ENABLE_LIVE_TRADING(self) -> bool:  # noqa: N802
        return self.features.enable_live_trading

    @property
    def ENABLE_PAPER_TRADING(self) -> bool:  # noqa: N802
        return self.features.enable_paper_trading

    @property
    def ENABLE_EVENT_REPLAY(self) -> bool:  # noqa: N802
        return self.features.enable_event_replay

    @property
    def ENABLE_RISK_GUARD(self) -> bool:  # noqa: N802
        return self.features.enable_risk_guard

    @property
    def ENABLE_FEATURE_STORE(self) -> bool:  # noqa: N802
        return self.features.enable_feature_store

    # CORS
    @property
    def CORS_ENABLED(self) -> bool:  # noqa: N802
        return self.cors.enabled

    # API
    @property
    def API_PREFIX(self) -> str:  # noqa: N802
        return self.api.prefix

    @property
    def API_DOCS_ENABLED(self) -> bool:  # noqa: N802
        return self.api.docs_enabled

    @property
    def API_REQUEST_TIMEOUT(self) -> int:  # noqa: N802
        return self.api.request_timeout_seconds

    # Rate limit
    @property
    def RATE_LIMIT_ENABLED(self) -> bool:  # noqa: N802
        return self.rate_limit.enabled

    @property
    def RATE_LIMIT_RPM(self) -> int:  # noqa: N802
        return self.rate_limit.requests_per_minute

    @property
    def RATE_LIMIT_BURST(self) -> int:  # noqa: N802
        return self.rate_limit.burst_size

    # Cache
    @property
    def CACHE_ENABLED(self) -> bool:  # noqa: N802
        return self.cache.enabled

    @property
    def CACHE_BACKEND(self) -> str:  # noqa: N802
        return self.cache.backend.value

    @property
    def CACHE_DEFAULT_TTL(self) -> int:  # noqa: N802
        return self.cache.default_ttl_seconds

    # Research
    @property
    def RESEARCH_WORKSPACE(self) -> str:  # noqa: N802
        return self.research.workspace_path

    @property
    def RESEARCH_MAX_JOBS(self) -> int:  # noqa: N802
        return self.research.max_parallel_jobs

    # AI Runtime
    @property
    def AI_RUNTIME_ENABLED(self) -> bool:  # noqa: N802
        return self.ai.enabled

    @property
    def AI_PROVIDER(self) -> str:  # noqa: N802
        return self.ai.provider

    @property
    def AI_MODEL_PATH(self) -> str:  # noqa: N802
        return self.ai.model_path or ""

    @property
    def AI_DEVICE(self) -> str:  # noqa: N802
        return self.ai.device

    @property
    def AI_TIMEOUT(self) -> int:  # noqa: N802
        return self.ai.timeout_seconds

    # Deployment
    @property
    def DEPLOYMENT_MODE(self) -> str:  # noqa: N802
        return self.deployment.mode.value

    @property
    def DEPLOYMENT_REGION(self) -> str:  # noqa: N802
        return self.deployment.region

    @property
    def INSTANCE_ID(self) -> str:  # noqa: N802
        return self.deployment.instance_id

    # Kubernetes
    @property
    def K8S_NAMESPACE(self) -> str:  # noqa: N802
        return self.kubernetes.namespace

    @property
    def K8S_SERVICE_NAME(self) -> str:  # noqa: N802
        return self.kubernetes.service_name

    @property
    def K8S_POD_NAME(self) -> str:  # noqa: N802
        return self.kubernetes.pod_name or ""

    # Storage
    @property
    def STORAGE_BACKEND(self) -> str:  # noqa: N802
        return self.storage.backend.value

    @property
    def STORAGE_BASE_PATH(self) -> str:  # noqa: N802
        return self.storage.base_path

    @property
    def STORAGE_BUCKET(self) -> str:  # noqa: N802
        return self.storage.bucket or ""

    # Compliance
    @property
    def AUDIT_LOG_ENABLED(self) -> bool:  # noqa: N802
        return self.compliance.enable_audit_log

    @property
    def AUDIT_RETAIN_DAYS(self) -> int:  # noqa: N802
        return self.compliance.retain_days

    @property
    def IMMUTABLE_RECORDS(self) -> bool:  # noqa: N802
        return self.compliance.immutable_records

    # ------ Production safety validation ------

    def validate_production(self) -> None:
        """
        Run production safety checks on this Settings instance.

        Raises:
            ValueError: When unsafe configuration detected.
        """
        validate_production_settings(self)

    def validate_environment(self) -> tuple[list[str], list[str]]:
        """
        Run environment-specific validation.

        Returns a tuple of (violations, warnings).
        """
        return validate_environment_settings(self)


# ============================================================================
# Cached Factory
# ============================================================================


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return singleton application settings.
    """
    settings = Settings()

    validate_production_settings(
        settings
    )

    return settings


def clear_settings_cache() -> None:
    """Invalidate the cached settings singleton.

    Useful in tests that modify ``os.environ`` and need a fresh
    ``Settings`` instance on the next call to :func:`get_settings`.
    """
    get_settings.cache_clear()
