from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LokiLogEntry:
    timestamp: str
    level: str
    message: str
    service: str
    labels: Dict[str, str] = field(default_factory=dict)


class LokiAdapter:
    def __init__(self, url: str = "http://localhost:3100"):
        self.url = url
        self._logs: List[LokiLogEntry] = []

    def push_log(
        self,
        level: str,
        message: str,
        service: str,
        labels: Optional[Dict[str, str]] = None,
    ):
        entry = LokiLogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            message=message,
            service=service,
            labels=labels or {},
        )
        self._logs.append(entry)

    def push_logs(self, logs: List[LokiLogEntry]):
        self._logs.extend(logs)

    def query_logs(
        self,
        service: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[LokiLogEntry]:
        results = self._logs
        if service:
            results = [l for l in results if l.service == service]
        if level:
            results = [l for l in results if l.level == level]
        return sorted(results, key=lambda l: l.timestamp, reverse=True)[:limit]

    def get_log_count(self) -> int:
        return len(self._logs)

    def format_for_loki(self) -> str:
        lines = []
        for log in self._logs:
            labels_str = ",".join(f'{k}="{v}"' for k, v in log.labels.items())
            lines.append(
                f'[{log.timestamp}] {{{labels_str}}} {log.level} [{log.service}] {log.message}'
            )
        return "\n".join(lines)

    def clear(self):
        self._logs.clear()
