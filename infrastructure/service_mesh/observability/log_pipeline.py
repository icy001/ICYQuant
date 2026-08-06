"""Log pipeline for ICYQuant Service Mesh.

Provides ``LogPipeline`` for processing access logs through a
pipeline: sidecar -> log pipeline -> storage -> dashboard.
Supports filtering, aggregation, search, and archiving.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .access_log import AccessLogEntry, AccessLogger

logger = logging.getLogger(__name__)


class LogFilter:
    """Filter for log entries."""

    def __init__(
        self,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        min_status: Optional[int] = None,
        max_status: Optional[int] = None,
        min_latency_ms: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        identity: Optional[str] = None,
    ) -> None:
        self.source = source
        self.destination = destination
        self.min_status = min_status
        self.max_status = max_status
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.identity = identity

    def matches(self, entry: AccessLogEntry) -> bool:
        if self.source and entry.source != self.source:
            return False
        if self.destination and entry.destination != self.destination:
            return False
        if self.min_status and entry.status_code < self.min_status:
            return False
        if self.max_status and entry.status_code > self.max_status:
            return False
        if self.min_latency_ms and entry.latency_ms < self.min_latency_ms:
            return False
        if self.max_latency_ms and entry.latency_ms > self.max_latency_ms:
            return False
        if self.identity and entry.identity != self.identity:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "min_status": self.min_status,
            "max_status": self.max_status,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "identity": self.identity,
        }


class LogStorage:
    """In-memory log storage with search and archive."""

    def __init__(self, max_entries: int = 100000) -> None:
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: List[Dict[str, Any]] = []
        self._archived: List[Dict[str, Any]] = []
        self._max_archived = 50000

    def store(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def search(
        self,
        query: str = "",
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        with self._lock:
            entries = list(self._entries)
        results = []
        for entry in entries:
            if query_lower:
                searchable = json.dumps(entry).lower()
                if query_lower not in searchable:
                    continue
            if filter_fn and not filter_fn(entry):
                continue
            results.append(entry)
        return results[-limit:]

    def archive(self, before: Optional[datetime] = None) -> int:
        with self._lock:
            if before is None:
                to_archive = list(self._entries)
                self._entries.clear()
            else:
                to_archive = []
                kept = []
                for entry in self._entries:
                    ts = entry.get("timestamp", "")
                    if ts and ts < before.isoformat():
                        to_archive.append(entry)
                    else:
                        kept.append(entry)
                self._entries = kept
            self._archived.extend(to_archive)
            if len(self._archived) > self._max_archived:
                self._archived = self._archived[-self._max_archived:]
            return len(to_archive)

    def get_archived(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._archived[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_entries": len(self._entries),
                "archived_entries": len(self._archived),
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._archived.clear()


class LogPipeline:
    """Processes access logs through a pipeline."""

    def __init__(
        self,
        access_logger: Optional[AccessLogger] = None,
        storage: Optional[LogStorage] = None,
    ) -> None:
        self._access_logger = access_logger or AccessLogger()
        self._storage = storage or LogStorage()
        self._filters: List[LogFilter] = []
        self._processors: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        self._lock = threading.RLock()
        self._pipeline_count = 0
        self._filtered_count = 0
        self._started = False

        # Wire access logger listener
        self._access_logger.add_listener(self._on_access_log)

    @property
    def access_logger(self) -> AccessLogger:
        return self._access_logger

    @property
    def storage(self) -> LogStorage:
        return self._storage

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._access_logger.start()
        self._started = True
        logger.info("Log pipeline started")

    def stop(self) -> None:
        self._access_logger.stop()
        self._started = False
        logger.info("Log pipeline stopped")

    def add_filter(self, log_filter: LogFilter) -> None:
        with self._lock:
            self._filters.append(log_filter)

    def remove_filter(self, log_filter: LogFilter) -> bool:
        with self._lock:
            if log_filter in self._filters:
                self._filters.remove(log_filter)
                return True
            return False

    def add_processor(
        self,
        fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        with self._lock:
            self._processors.append(fn)

    def _on_access_log(self, entry: AccessLogEntry) -> None:
        with self._lock:
            filters = list(self._filters)
            processors = list(self._processors)

        # Apply filters
        for f in filters:
            if not f.matches(entry):
                with self._lock:
                    self._filtered_count += 1
                return

        # Convert to dict
        data = entry.to_dict()

        # Apply processors
        for proc in processors:
            try:
                data = proc(data)
            except Exception as exc:
                logger.warning("Log processor failed: %s", exc)

        # Store
        self._storage.store(data)
        with self._lock:
            self._pipeline_count += 1

    def search(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        return self._storage.search(query=query, limit=limit)

    def archive(self, before: Optional[datetime] = None) -> int:
        return self._storage.archive(before)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "pipeline_count": self._pipeline_count,
                "filtered_count": self._filtered_count,
                "filter_count": len(self._filters),
                "processor_count": len(self._processors),
                "storage": self._storage.get_stats(),
                "access_logger": self._access_logger.get_stats(),
            }

    def clear(self) -> None:
        self._storage.clear()
        with self._lock:
            self._pipeline_count = 0
            self._filtered_count = 0
