"""Access logging for ICYQuant Service Mesh.

Provides ``AccessLogEntry`` and ``AccessLogger`` for recording
structured access logs with source, destination, latency, retry,
response code, and identity information.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class AccessLogEntry:
    """A single access log entry."""

    def __init__(
        self,
        source: str = "",
        destination: str = "",
        method: str = "",
        path: str = "",
        status_code: int = 200,
        latency_ms: float = 0.0,
        retry_count: int = 0,
        trace_id: str = "",
        span_id: str = "",
        identity: str = "",
        protocol: str = "http",
        request_size: int = 0,
        response_size: int = 0,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.source = source
        self.destination = destination
        self.method = method
        self.path = path
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.retry_count = retry_count
        self.trace_id = trace_id
        self.span_id = span_id
        self.identity = identity
        self.protocol = protocol
        self.request_size = request_size
        self.response_size = response_size
        self.headers = headers or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def is_retry(self) -> bool:
        return self.retry_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "identity": self.identity,
            "protocol": self.protocol,
            "request_size": self.request_size,
            "response_size": self.response_size,
            "headers": dict(self.headers),
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_structured_log(self) -> str:
        """Format as structured log line."""
        return json.dumps({
            "timestamp": self.timestamp.isoformat(),
            "level": "ERROR" if self.is_error else "INFO",
            "source": self.source,
            "destination": self.destination,
            "method": self.method,
            "path": self.path,
            "status": self.status_code,
            "latency_ms": self.latency_ms,
            "retries": self.retry_count,
            "trace_id": self.trace_id,
            "identity": self.identity,
        })


class AccessLogger:
    """Collects and dispatches access log entries."""

    def __init__(
        self,
        max_entries: int = 50000,
        flush_interval_s: float = 5.0,
    ) -> None:
        self._max_entries = max_entries
        self._flush_interval_s = flush_interval_s
        self._lock = threading.RLock()
        self._entries: List[AccessLogEntry] = []
        self._listeners: List[Callable[[AccessLogEntry], None]] = []
        self._log_count = 0
        self._error_count = 0
        self._retry_count = 0
        self._last_flush = time.monotonic()
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Access logger started")

    def stop(self) -> None:
        self._started = False
        logger.info("Access logger stopped")

    def log(self, entry: AccessLogEntry) -> None:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
            self._log_count += 1
            if entry.is_error:
                self._error_count += 1
            if entry.is_retry:
                self._retry_count += 1

        for listener in self._listeners:
            try:
                listener(entry)
            except Exception as exc:
                logger.warning("Access log listener failed: %s", exc)

    def log_request(
        self,
        source: str,
        destination: str,
        method: str = "GET",
        path: str = "/",
        status_code: int = 200,
        latency_ms: float = 0.0,
        retry_count: int = 0,
        trace_id: str = "",
        identity: str = "",
        **kwargs: Any,
    ) -> AccessLogEntry:
        entry = AccessLogEntry(
            source=source,
            destination=destination,
            method=method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            retry_count=retry_count,
            trace_id=trace_id,
            identity=identity,
            **kwargs,
        )
        self.log(entry)
        return entry

    def add_listener(self, fn: Callable[[AccessLogEntry], None]) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[AccessLogEntry], None]) -> bool:
        if fn in self._listeners:
            self._listeners.remove(fn)
            return True
        return False

    def get_entries(
        self,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        status_code: Optional[int] = None,
        is_error: Optional[bool] = None,
        limit: int = 100,
    ) -> List[AccessLogEntry]:
        with self._lock:
            entries = list(self._entries)
        results = []
        for entry in entries:
            if source and entry.source != source:
                continue
            if destination and entry.destination != destination:
                continue
            if status_code and entry.status_code != status_code:
                continue
            if is_error is not None and entry.is_error != is_error:
                continue
            results.append(entry)
        return results[-limit:]

    def search(
        self,
        query: str,
        limit: int = 100,
    ) -> List[AccessLogEntry]:
        query_lower = query.lower()
        with self._lock:
            entries = list(self._entries)
        results = []
        for entry in entries:
            searchable = f"{entry.source} {entry.destination} {entry.method} {entry.path} {entry.identity}".lower()
            if query_lower in searchable:
                results.append(entry)
        return results[-limit:]

    def flush(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._entries)
            self._entries.clear()
            self._last_flush = time.monotonic()
        return {
            "flushed": len(entries),
            "log_count": self._log_count,
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "total_entries": len(self._entries),
                "log_count": self._log_count,
                "error_count": self._error_count,
                "retry_count": self._retry_count,
                "listener_count": len(self._listeners),
                "error_rate": (
                    self._error_count / self._log_count
                    if self._log_count > 0
                    else 0.0
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._log_count = 0
            self._error_count = 0
            self._retry_count = 0
