"""SLI (Service Level Indicator) for ICYQuant Service Mesh.

Provides ``SLI`` and ``SLICalculator`` for computing real-time
availability, latency, throughput, and error metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SLIType(str):
    """SLI types."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class SLI:
    """A service level indicator."""

    def __init__(
        self,
        sli_id: str,
        sli_type: str,
        service: str = "",
        target: float = 0.0,
        window_s: float = 300.0,
    ) -> None:
        self.sli_id = sli_id
        self.sli_type = sli_type
        self.service = service
        self.target = target
        self.window_s = window_s
        self._lock = threading.Lock()
        self._samples: List[Dict[str, Any]] = []
        self._max_samples = 10000

    def record(self, value: float, timestamp: Optional[float] = None) -> None:
        ts = timestamp or time.monotonic()
        with self._lock:
            self._samples.append({"timestamp": ts, "value": value})
            if len(self._samples) > self._max_samples:
                self._samples = self._samples[-self._max_samples:]

    def record_request(self, success: bool, latency_ms: float = 0.0) -> None:
        if self.sli_type == SLIType.AVAILABILITY:
            self.record(1.0 if success else 0.0)
        elif self.sli_type == SLIType.LATENCY:
            self.record(latency_ms)
        elif self.sli_type == SLIType.ERROR_RATE:
            self.record(0.0 if success else 1.0)
        elif self.sli_type == SLIType.THROUGHPUT:
            self.record(1.0)

    def compute(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_s
            recent = [s for s in self._samples if s["timestamp"] >= cutoff]

        if not recent:
            return {
                "sli_id": self.sli_id,
                "sli_type": self.sli_type,
                "service": self.service,
                "value": 0.0,
                "sample_count": 0,
                "window_s": self.window_s,
                "target": self.target,
                "meeting_target": False,
                "timestamp": datetime.utcnow().isoformat(),
            }

        values = [s["value"] for s in recent]
        if self.sli_type == SLIType.AVAILABILITY:
            value = sum(values) / len(values)
        elif self.sli_type == SLIType.LATENCY:
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * 0.99)
            value = sorted_vals[min(idx, len(sorted_vals) - 1)]
        elif self.sli_type == SLIType.ERROR_RATE:
            value = sum(values) / len(values)
        elif self.sli_type == SLIType.THROUGHPUT:
            value = len(values) / self.window_s
        else:
            value = sum(values) / len(values)

        meeting = True
        if self.sli_type in (SLIType.AVAILABILITY, SLIType.THROUGHPUT):
            meeting = value >= self.target
        else:
            meeting = value <= self.target

        return {
            "sli_id": self.sli_id,
            "sli_type": self.sli_type,
            "service": self.service,
            "value": value,
            "sample_count": len(recent),
            "window_s": self.window_s,
            "target": self.target,
            "meeting_target": meeting,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.compute()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sli_id": self.sli_id,
                "sli_type": self.sli_type,
                "service": self.service,
                "target": self.target,
                "sample_count": len(self._samples),
                "window_s": self.window_s,
            }

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()


class SLICalculator:
    """Manages and computes multiple SLIs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._slis: Dict[str, SLI] = {}
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("SLI calculator started")

    def stop(self) -> None:
        self._started = False
        logger.info("SLI calculator stopped")

    def register_sli(self, sli: SLI) -> None:
        with self._lock:
            self._slis[sli.sli_id] = sli

    def unregister_sli(self, sli_id: str) -> bool:
        with self._lock:
            if sli_id in self._slis:
                del self._slis[sli_id]
                return True
            return False

    def get_sli(self, sli_id: str) -> Optional[SLI]:
        with self._lock:
            return self._slis.get(sli_id)

    def list_slis(self) -> List[SLI]:
        with self._lock:
            return list(self._slis.values())

    def compute_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            slis = list(self._slis.values())
        return [sli.compute() for sli in slis]

    def record_request(
        self,
        service: str,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        with self._lock:
            slis = list(self._slis.values())
        for sli in slis:
            if sli.service == service or not sli.service:
                sli.record_request(success, latency_ms)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "sli_count": len(self._slis),
            }

    def clear(self) -> None:
        with self._lock:
            for sli in self._slis.values():
                sli.clear()
