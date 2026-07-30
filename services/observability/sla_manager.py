from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class SLAType(Enum):
    RESPONSE_TIME = "RESPONSE_TIME"
    AVAILABILITY = "AVAILABILITY"
    RESOLUTION_TIME = "RESOLUTION_TIME"
    SUPPORT_TIME = "SUPPORT_TIME"


class SLAPriority(Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


@dataclass
class SLADefinition:
    sla_id: str
    name: str
    service: str
    sla_type: str
    target_value: float
    unit: str
    priority: str
    description: str = ""


@dataclass
class SLAIncident:
    incident_id: str
    sla_id: str
    title: str
    description: str
    priority: str
    reported_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_time_hours: float = 0
    met_sla: bool = True
    status: str = "OPEN"


@dataclass
class SLAReport:
    period_start: datetime
    period_end: datetime
    total_incidents: int
    sla_met_count: int
    sla_breach_count: int
    compliance_rate: float
    by_sla: Dict[str, Dict]


class SLAManager:
    def __init__(self):
        self._slas: Dict[str, SLADefinition] = {}
        self._incidents: List[SLAIncident] = []

    def define_sla(
        self,
        sla_id: str,
        name: str,
        service: str,
        sla_type: str,
        target_value: float,
        unit: str,
        priority: str = SLAPriority.P3.value,
        description: str = "",
    ) -> SLADefinition:
        sla = SLADefinition(
            sla_id=sla_id,
            name=name,
            service=service,
            sla_type=sla_type,
            target_value=target_value,
            unit=unit,
            priority=priority,
            description=description,
        )
        self._slas[sla_id] = sla
        return sla

    def report_incident(
        self,
        sla_id: str,
        title: str,
        description: str,
        priority: str = SLAPriority.P3.value,
        reported_at: Optional[datetime] = None,
    ) -> SLAIncident:
        import uuid
        incident = SLAIncident(
            incident_id=uuid.uuid4().hex[:12],
            sla_id=sla_id,
            title=title,
            description=description,
            priority=priority,
            reported_at=reported_at or datetime.now(),
        )
        self._incidents.append(incident)
        return incident

    def resolve_incident(
        self,
        incident_id: str,
        resolved_at: Optional[datetime] = None,
    ) -> SLAIncident:
        for inc in self._incidents:
            if inc.incident_id == incident_id:
                inc.resolved_at = resolved_at or datetime.now()
                inc.status = "RESOLVED"
                delta = (inc.resolved_at - inc.reported_at).total_seconds() / 3600
                inc.resolution_time_hours = round(delta, 2)

                sla = self._slas.get(inc.sla_id)
                if sla:
                    inc.met_sla = delta <= sla.target_value
                return inc
        raise ValueError(f"Incident {incident_id} not found")

    def get_open_incidents(self) -> List[SLAIncident]:
        return [i for i in self._incidents if i.status == "OPEN"]

    def get_incidents_by_sla(self, sla_id: str) -> List[SLAIncident]:
        return [i for i in self._incidents if i.sla_id == sla_id]

    def get_sla_status(self, sla_id: str) -> Dict:
        sla = self._slas.get(sla_id)
        if not sla:
            return {"error": f"SLA {sla_id} not found"}

        incidents = self.get_incidents_by_sla(sla_id)
        resolved = [i for i in incidents if i.resolved_at]
        met = [i for i in resolved if i.met_sla]
        total = len(resolved)

        compliance = len(met) / total if total > 0 else 1.0

        return {
            "sla_id": sla_id,
            "name": sla.name,
            "service": sla.service,
            "target": f"{sla.target_value} {sla.unit}",
            "priority": sla.priority,
            "total_incidents": len(incidents),
            "resolved": total,
            "met": len(met),
            "breached": total - len(met),
            "compliance_rate": round(compliance, 4),
        }

    def generate_report(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> SLAReport:
        start = period_start or datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = period_end or datetime.now()

        incidents = [i for i in self._incidents if start <= i.reported_at <= end]
        resolved = [i for i in incidents if i.resolved_at]
        met = [i for i in resolved if i.met_sla]
        total = len(resolved)

        by_sla: Dict[str, Dict] = {}
        for sla_id in self._slas:
            sla_incidents = [i for i in incidents if i.sla_id == sla_id]
            sla_resolved = [i for i in sla_incidents if i.resolved_at]
            sla_met = [i for i in sla_resolved if i.met_sla]
            sla_total = len(sla_resolved)
            by_sla[sla_id] = {
                "total_incidents": len(sla_incidents),
                "resolved": sla_total,
                "met": len(sla_met),
                "breached": sla_total - len(sla_met),
                "compliance": len(sla_met) / sla_total if sla_total > 0 else 1.0,
            }

        return SLAReport(
            period_start=start,
            period_end=end,
            total_incidents=len(incidents),
            sla_met_count=len(met),
            sla_breach_count=total - len(met),
            compliance_rate=round(len(met) / total, 4) if total > 0 else 1.0,
            by_sla=by_sla,
        )

    def list_slas(self) -> List[SLADefinition]:
        return list(self._slas.values())

    def list_incidents(self, limit: int = 50) -> List[SLAIncident]:
        return sorted(self._incidents, key=lambda i: i.reported_at, reverse=True)[:limit]
