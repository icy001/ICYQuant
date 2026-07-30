from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta


class SLOStatus(Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    NOT_STARTED = "NOT_STARTED"


class SLOType(Enum):
    AVAILABILITY = "AVAILABILITY"
    LATENCY = "LATENCY"
    ERROR_RATE = "ERROR_RATE"
    THROUGHPUT = "THROUGHPUT"


@dataclass
class SLODefinition:
    slo_id: str
    name: str
    service: str
    slo_type: str
    target_value: float
    window_days: int
    warning_threshold: float = 0.95
    critical_threshold: float = 0.99
    description: str = ""


@dataclass
class SLOStatusReport:
    slo_id: str
    name: str
    service: str
    slo_type: str
    status: str
    current_value: float
    target_value: float
    remaining_error_budget: float
    total_events: int
    good_events: int
    bad_events: int
    period_start: datetime
    period_end: datetime
    message: str = ""


class SLOManager:
    def __init__(self):
        self._slos: Dict[str, SLODefinition] = {}
        self._events: Dict[str, List[Dict]] = {}

    def define_slo(
        self,
        slo_id: str,
        name: str,
        service: str,
        slo_type: str,
        target_value: float,
        window_days: int = 30,
        warning_threshold: float = 0.95,
        critical_threshold: float = 0.99,
        description: str = "",
    ) -> SLODefinition:
        slo = SLODefinition(
            slo_id=slo_id,
            name=name,
            service=service,
            slo_type=slo_type,
            target_value=target_value,
            window_days=window_days,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            description=description,
        )
        self._slos[slo_id] = slo
        self._events[slo_id] = []
        return slo

    def record_event(
        self,
        slo_id: str,
        is_good: bool,
        timestamp: Optional[datetime] = None,
        value: Optional[float] = None,
    ):
        if slo_id not in self._events:
            self._events[slo_id] = []
        self._events[slo_id].append({
            "timestamp": timestamp or datetime.now(),
            "is_good": is_good,
            "value": value,
        })

    def record_availability_event(self, slo_id: str, available: bool):
        self.record_event(slo_id, is_good=available)

    def record_latency_event(self, slo_id: str, latency_ms: float, target_ms: float):
        is_good = latency_ms <= target_ms
        self.record_event(slo_id, is_good=is_good, value=latency_ms)

    def get_status(self, slo_id: str) -> SLOStatusReport:
        slo = self._slos.get(slo_id)
        if not slo:
            raise ValueError(f"SLO {slo_id} not found")

        events = self._events.get(slo_id, [])
        if not events:
            return SLOStatusReport(
                slo_id=slo_id,
                name=slo.name,
                service=slo.service,
                slo_type=slo.slo_type,
                status=SLOStatus.NOT_STARTED.value,
                current_value=0,
                target_value=slo.target_value,
                remaining_error_budget=1.0,
                total_events=0,
                good_events=0,
                bad_events=0,
                period_start=datetime.now(),
                period_end=datetime.now(),
                message="No events recorded yet",
            )

        now = datetime.now()
        window_start = now - timedelta(days=slo.window_days)
        window_events = [e for e in events if e["timestamp"] >= window_start]

        total = len(window_events)
        good = sum(1 for e in window_events if e["is_good"])
        bad = total - good

        if total > 0:
            current = good / total
        else:
            current = 1.0

        error_budget = max(0, 1.0 - slo.target_value)
        consumed = (1.0 - current) / error_budget if error_budget > 0 else 0
        remaining = max(0, 1.0 - consumed)

        if current >= slo.target_value:
            status = SLOStatus.ON_TRACK.value
            message = f"SLO on track: {current:.4%} >= {slo.target_value:.4%}"
        elif current >= slo.target_value * slo.warning_threshold:
            status = SLOStatus.AT_RISK.value
            message = f"SLO at risk: {current:.4%} < {slo.target_value:.4%}"
        else:
            status = SLOStatus.BREACHED.value
            message = f"SLO breached: {current:.4%} < {slo.target_value:.4%}"

        return SLOStatusReport(
            slo_id=slo_id,
            name=slo.name,
            service=slo.service,
            slo_type=slo.slo_type,
            status=status,
            current_value=round(current, 6),
            target_value=slo.target_value,
            remaining_error_budget=round(remaining, 4),
            total_events=total,
            good_events=good,
            bad_events=bad,
            period_start=window_start,
            period_end=now,
            message=message,
        )

    def get_all_statuses(self) -> List[SLOStatusReport]:
        return [self.get_status(slo_id) for slo_id in self._slos]

    def list_slos(self) -> List[SLODefinition]:
        return list(self._slos.values())

    def delete_slo(self, slo_id: str):
        self._slos.pop(slo_id, None)
        self._events.pop(slo_id, None)
