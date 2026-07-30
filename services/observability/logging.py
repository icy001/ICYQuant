from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
from collections import defaultdict


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    APPLICATION = "APPLICATION"
    TRADING = "TRADING"
    RISK = "RISK"
    AUDIT = "AUDIT"
    AI = "AI"
    SYSTEM = "SYSTEM"


@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    category: str
    service: str
    message: str
    trace_id: Optional[str] = None
    order_id: Optional[str] = None
    strategy_id: Optional[str] = None
    account_id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class CentralizedLogger:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._logs: List[LogEntry] = []
        self._logs_by_trace: Dict[str, List[LogEntry]] = defaultdict(list)
        self._logs_by_level: Dict[str, List[LogEntry]] = defaultdict(list)
        self._logs_by_category: Dict[str, List[LogEntry]] = defaultdict(list)

    def log(
        self,
        level: str,
        message: str,
        category: str = LogCategory.APPLICATION.value,
        trace_id: Optional[str] = None,
        order_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        account_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> LogEntry:
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            service=self.service_name,
            message=message,
            trace_id=trace_id,
            order_id=order_id,
            strategy_id=strategy_id,
            account_id=account_id,
            metadata=metadata or {},
        )
        self._logs.append(entry)
        if trace_id:
            self._logs_by_trace[trace_id].append(entry)
        self._logs_by_level[level].append(entry)
        self._logs_by_category[category].append(entry)
        return entry

    def debug(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.DEBUG.value, message, **kwargs)

    def info(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.INFO.value, message, **kwargs)

    def warning(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.WARNING.value, message, **kwargs)

    def error(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.ERROR.value, message, **kwargs)

    def critical(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.CRITICAL.value, message, **kwargs)

    def query_by_trace(self, trace_id: str) -> List[LogEntry]:
        return self._logs_by_trace.get(trace_id, [])

    def query_by_level(self, level: str) -> List[LogEntry]:
        return self._logs_by_level.get(level, [])

    def query_by_category(self, category: str) -> List[LogEntry]:
        return self._logs_by_category.get(category, [])

    def query_by_order(self, order_id: str) -> List[LogEntry]:
        return [l for l in self._logs if l.order_id == order_id]

    def query_by_strategy(self, strategy_id: str) -> List[LogEntry]:
        return [l for l in self._logs if l.strategy_id == strategy_id]

    def query_by_account(self, account_id: str) -> List[LogEntry]:
        return [l for l in self._logs if l.account_id == account_id]

    def get_recent(self, limit: int = 50) -> List[LogEntry]:
        return sorted(self._logs, key=lambda l: l.timestamp, reverse=True)[:limit]

    def get_all(self) -> List[LogEntry]:
        return list(self._logs)

    def clear(self):
        self._logs.clear()
        self._logs_by_trace.clear()
        self._logs_by_level.clear()
        self._logs_by_category.clear()


class LogManager:
    def __init__(self):
        self._loggers: Dict[str, CentralizedLogger] = {}

    def get_logger(self, service_name: str) -> CentralizedLogger:
        if service_name not in self._loggers:
            self._loggers[service_name] = CentralizedLogger(service_name)
        return self._loggers[service_name]

    def query_by_trace(self, trace_id: str) -> List[LogEntry]:
        results = []
        for logger in self._loggers.values():
            results.extend(logger.query_by_trace(trace_id))
        return sorted(results, key=lambda l: l.timestamp)

    def query_by_level(self, level: str) -> List[LogEntry]:
        results = []
        for logger in self._loggers.values():
            results.extend(logger.query_by_level(level))
        return sorted(results, key=lambda l: l.timestamp, reverse=True)

    def query_by_category(self, category: str) -> List[LogEntry]:
        results = []
        for logger in self._loggers.values():
            results.extend(logger.query_by_category(category))
        return sorted(results, key=lambda l: l.timestamp, reverse=True)

    def query_by_order(self, order_id: str) -> List[LogEntry]:
        results = []
        for logger in self._loggers.values():
            results.extend(logger.query_by_order(order_id))
        return sorted(results, key=lambda l: l.timestamp)

    def get_all_logs(self, limit: int = 100) -> List[LogEntry]:
        results = []
        for logger in self._loggers.values():
            results.extend(logger.get_all())
        return sorted(results, key=lambda l: l.timestamp, reverse=True)[:limit]
