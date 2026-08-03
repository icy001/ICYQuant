"""Platform-wide constants."""
from enum import Enum
from typing import Final

APP_NAME: Final[str] = "ICYQuant"
APP_VERSION: Final[str] = "0.4.0-alpha2"
DEFAULT_ENCODING: Final[str] = "utf-8"
DEFAULT_TIMEOUT: Final[int] = 30
MAX_RETRIES: Final[int] = 3
DEFAULT_PAGE_SIZE: Final[int] = 100
MAX_PAGE_SIZE: Final[int] = 1000

class ModuleType(str, Enum):
    MARKET = "market"
    RESEARCH = "research"
    AI = "ai"
    BACKTEST = "backtest"
    OMS = "oms"
    EMS = "ems"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    DATA = "data"
    OBSERVABILITY = "observability"
    SECURITY = "security"
    PLATFORM = "platform"
    EXTENSION = "extension"

class ServiceStatus(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"

class ErrorCode(int, Enum):
    OK = 0
    INTERNAL_ERROR = 1000
    CONFIG_ERROR = 1001
    INITIALIZATION_ERROR = 1002
    DEPENDENCY_ERROR = 1003
    VALIDATION_ERROR = 2000
    AUTHENTICATION_ERROR = 2001
    AUTHORIZATION_ERROR = 2002
    NOT_FOUND = 3000
    CONFLICT = 3001
    RATE_LIMITED = 3002
    MARKET_DATA_ERROR = 4000
    EXECUTION_ERROR = 4001
    RISK_VIOLATION = 4002
    NETWORK_ERROR = 5000
    DATABASE_ERROR = 5001
    REDIS_ERROR = 5002
    KAFKA_ERROR = 5003
