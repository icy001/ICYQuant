"""SLO (Service Level Objective) for ICYQuant Service Mesh.

Provides ``SLO``, ``ErrorBudget``, and ``SLOMonitor`` for
tracking availability, latency, and error budget compliance.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .sli import SLI, SLIType, SLICalculator

logger = logging.getLogger(__name__)


class SLOStatus(str):
    """SLO status."""

    OK = "ok"
    AT_RISK = "at_risk"
    VIOLATED = "violated"


class ErrorBudget:
    """Error budget for an SLO."""

    def __init__(
        self,
        target: float = 0.999,
        window_days: int = 30,
    ) -> None:
        self.target = target
        self.window_days = window_days
        self._lock = threading.Lock()
        self._total_requests = 0
        self._good_requests = 0

    @property
    def allowed_errors(self) -> float:
        return max(0.0, self._total_requests * (1.0 - self.target))

    @property
    def actual_errors(self) -> int:
        return self._total_requests - self._good_requests

    @property
    def remaining_budget(self) -> float:
        allowed = self.allowed_errors
        if allowed == 0:
            return 0.0
        return max(0.0, (allowed - self.actual_errors) / allowed)

    @property
    def consumed_budget(self) -> float:
        allowed = self.allowed_errors
        if allowed == 0:
            return 0.0
        return min(1.0, self.actual_errors / allowed)

    def record(self, success: bool) -> None:
        with self._lock:
            self._total_requests += 1
            if success:
                self._good_requests += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "target": self.target,
                "window_days": self.window_days,
                "total_requests": self._total_requests,
                "good_requests": self._good_requests,
                "error_requests": self.actual_errors,
                "allowed_errors": self.allowed_errors,
                "remaining_budget": self.remaining_budget,
                "consumed_budget": self.consumed_budget,
            }

    def reset(self) -> None:
        with self._lock:
            self._total_requests = 0
            self._good_requests = 0


class SLO:
    """A service level objective."""

    def __init__(
        self,
        slo_id: str,
        name: str = "",
        service: str = "",
        sli_type: str = SLIType.AVAILABILITY,
        target: float = 0.999,
        window_days: int = 30,
        description: str = "",
    ) -> None:
        self.slo_id = slo_id
        self.name = name or slo_id
        self.service = service
        self.sli_type = sli_type
        self.target = target
        self.window_days = window_days
        self.description = description
        self.error_budget = ErrorBudget(target=target, window_days=window_days)
        self.sli = SLI(
            sli_id=f"{slo_id}-sli",
            sli_type=sli_type,
            service=service,
            target=target,
        )
        self._lock = threading.Lock()
        self._violations: List[Dict[str, Any]] = []
        self._max_violations = 100

    def record_request(self, success: bool, latency_ms: float = 0.0) -> None:
        self.error_budget.record(success)
        self.sli.record_request(success, latency_ms)

    def evaluate(self) -> Dict[str, Any]:
        sli_result = self.sli.compute()
        budget = self.error_budget.get_stats()
        sli_value = sli_result["value"]

        if self.sli_type in (SLIType.AVAILABILITY, SLIType.THROUGHPUT):
            status = SLOStatus.OK
            if sli_value < self.target:
                status = SLOStatus.VIOLATED
            elif budget["remaining_budget"] < 0.25:
                status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.OK
            if sli_value > self.target:
                status = SLOStatus.VIOLATED
            elif budget["remaining_budget"] < 0.25:
                status = SLOStatus.AT_RISK

        if status == SLOStatus.VIOLATED:
            with self._lock:
                self._violations.append({
                    "slo_id": self.slo_id,
                    "metric": self.sli_type,
                    "expected": self.target,
                    "actual": sli_value,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                if len(self._violations) > self._max_violations:
                    self._violations = self._violations[-self._max_violations:]

        return {
            "slo_id": self.slo_id,
            "name": self.name,
            "service": self.service,
            "sli_type": self.sli_type,
            "target": self.target,
            "current_value": sli_value,
            "status": status,
            "error_budget": budget,
            "violations": len(self._violations),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_violations(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._violations[-limit:])

    def to_dict(self) -> Dict[str, Any]:
        return self.evaluate()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "name": self.name,
            "service": self.service,
            "sli_type": self.sli_type,
            "target": self.target,
            "violation_count": len(self._violations),
            "budget": self.error_budget.get_stats(),
        }


class SLOMonitor:
    """Monitors all SLOs across the mesh."""

    def __init__(self, sli_calculator: Optional[SLICalculator] = None) -> None:
        self._sli_calculator = sli_calculator or SLICalculator()
        self._lock = threading.RLock()
        self._slos: Dict[str, SLO] = {}
        self._violation_count = 0
        self._evaluation_count = 0
        self._started = False

    @property
    def sli_calculator(self) -> SLICalculator:
        return self._sli_calculator

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._sli_calculator.start()
        self._started = True
        logger.info("SLO monitor started")

    def stop(self) -> None:
        self._sli_calculator.stop()
        self._started = False
        logger.info("SLO monitor stopped")

    def register_slo(self, slo: SLO) -> None:
        with self._lock:
            self._slos[slo.slo_id] = slo
            self._sli_calculator.register_sli(slo.sli)

    def unregister_slo(self, slo_id: str) -> bool:
        with self._lock:
            if slo_id in self._slos:
                slo = self._slos.pop(slo_id)
                self._sli_calculator.unregister_sli(slo.sli.sli_id)
                return True
            return False

    def get_slo(self, slo_id: str) -> Optional[SLO]:
        with self._lock:
            return self._slos.get(slo_id)

    def list_slos(self) -> List[SLO]:
        with self._lock:
            return list(self._slos.values())

    def record_request(
        self,
        service: str,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        self._sli_calculator.record_request(service, success, latency_ms)
        with self._lock:
            for slo in self._slos.values():
                if not slo.service or slo.service == service:
                    slo.record_request(success, latency_ms)

    def evaluate_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            slos = list(self._slos.values())

        results = []
        for slo in slos:
            result = slo.evaluate()
            results.append(result)
            if result["status"] == SLOStatus.VIOLATED:
                with self._lock:
                    self._violation_count += 1
            with self._lock:
                self._evaluation_count += 1
        return results

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "slo_count": len(self._slos),
                "violation_count": self._violation_count,
                "evaluation_count": self._evaluation_count,
                "sli_calculator": self._sli_calculator.get_stats(),
            }
