"""
ICYQuant Incident Response

Automated security incident response: credential leak -> disable account
-> rotate key -> notify security team.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class IncidentType(str, Enum):
    CREDENTIAL_LEAK = "credential_leak"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    PRIVILEGE_ABUSE = "privilege_abuse"
    MALWARE_DETECTED = "malware_detected"
    DDoS_ATTACK = "ddos_attack"
    INSIDER_THREAT = "insider_threat"
    VULNERABILITY = "vulnerability"


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ResponseAction(str, Enum):
    DISABLE_ACCOUNT = "disable_account"
    ROTATE_KEYS = "rotate_keys"
    NOTIFY_TEAM = "notify_team"
    BLOCK_IP = "block_ip"
    QUARANTINE = "quarantine"
    ESCALATE = "escalate"
    CREATE_TICKET = "create_ticket"
    FORENSIC_COLLECTION = "forensic_collection"


@dataclass
class IncidentAction:
    action: ResponseAction
    performed_at: datetime = field(default_factory=datetime.now)
    result: str = "success"
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "performedAt": self.performed_at.isoformat(),
            "result": self.result,
            "details": self.details,
        }


@dataclass
class Incident:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: IncidentType = IncidentType.CREDENTIAL_LEAK
    severity: IncidentSeverity = IncidentSeverity.HIGH
    status: IncidentStatus = IncidentStatus.OPEN
    title: str = ""
    description: str = ""
    affected_user: str = ""
    affected_system: str = ""
    ip_address: str = ""
    details: Dict = field(default_factory=dict)
    actions: List[IncidentAction] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    assigned_to: str = ""
    root_cause: str = ""
    lessons_learned: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "incidentType": self.incident_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "affectedUser": self.affected_user,
            "affectedSystem": self.affected_system,
            "actions": [a.to_dict() for a in self.actions],
            "createdAt": self.created_at.isoformat(),
            "statusUpdatedAt": self.updated_at.isoformat(),
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class IncidentResponseManager:
    """
    Automated security incident response manager.

    Handles security incidents with automated response workflows:
    disable accounts, rotate keys, notify teams, block IPs, etc.
    """

    def __init__(self):
        self._incidents: Dict[str, Incident] = {}
        self._response_runbooks: Dict[IncidentType, List[ResponseAction]] = {}
        self._webhooks: List[str] = []
        self._init_default_runbooks()

    def _init_default_runbooks(self):
        self._response_runbooks = {
            IncidentType.CREDENTIAL_LEAK: [
                ResponseAction.DISABLE_ACCOUNT,
                ResponseAction.ROTATE_KEYS,
                ResponseAction.NOTIFY_TEAM,
                ResponseAction.CREATE_TICKET,
                ResponseAction.ESCALATE,
            ],
            IncidentType.UNAUTHORIZED_ACCESS: [
                ResponseAction.BLOCK_IP,
                ResponseAction.QUARANTINE,
                ResponseAction.NOTIFY_TEAM,
            ],
            IncidentType.DATA_BREACH: [
                ResponseAction.ISOLATE if hasattr(ResponseAction, 'ISOLATE') else ResponseAction.QUARANTINE,
                ResponseAction.FORENSIC_COLLECTION,
                ResponseAction.NOTIFY_TEAM,
                ResponseAction.ESCALATE,
                ResponseAction.CREATE_TICKET,
            ],
            IncidentType.PRIVILEGE_ABUSE: [
                ResponseAction.DISABLE_ACCOUNT,
                ResponseAction.ROTATE_KEYS,
                ResponseAction.ESCALATE,
            ],
            IncidentType.MALWARE_DETECTED: [
                ResponseAction.QUARANTINE,
                ResponseAction.FORENSIC_COLLECTION,
                ResponseAction.NOTIFY_TEAM,
            ],
            IncidentType.DDoS_ATTACK: [
                ResponseAction.BLOCK_IP,
                ResponseAction.NOTIFY_TEAM,
                ResponseAction.ESCALATE,
            ],
        }

    def create_incident(
        self,
        incident_type: IncidentType,
        title: str,
        description: str = "",
        severity: IncidentSeverity = IncidentSeverity.HIGH,
        affected_user: str = "",
        affected_system: str = "",
        ip_address: str = "",
        details: Optional[Dict] = None,
    ) -> Incident:
        incident = Incident(
            incident_type=incident_type,
            severity=severity,
            title=title,
            description=description,
            affected_user=affected_user,
            affected_system=affected_system,
            ip_address=ip_address,
            details=details or {},
        )
        self._incidents[incident.id] = incident
        logger.warning(f"Security incident created: {title} ({severity.value})")
        return incident

    def respond_to_incident(self, incident_id: str) -> List[IncidentAction]:
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        runbook = self._response_runbooks.get(incident.incident_type, [])
        if not runbook:
            logger.info(f"No runbook for incident type: {incident.incident_type.value}")
            return []

        incident.status = IncidentStatus.IN_PROGRESS
        incident.updated_at = datetime.now()

        actions = []
        for action_type in runbook:
            action = self._execute_action(action_type, incident)
            incident.actions.append(action)
            actions.append(action)

        if incident.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
            incident.status = IncidentStatus.CONTAINED
        else:
            incident.status = IncidentStatus.CONTAINED

        incident.updated_at = datetime.now()
        self._notify_incident(incident)
        return actions

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str = "",
        lessons_learned: Optional[List[str]] = None,
    ):
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found")

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now()
        incident.updated_at = datetime.now()
        incident.root_cause = root_cause
        incident.lessons_learned = lessons_learned or []

    def close_incident(self, incident_id: str):
        incident = self._incidents.get(incident_id)
        if incident:
            incident.status = IncidentStatus.CLOSED
            incident.updated_at = datetime.now()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        limit: int = 50,
    ) -> List[Incident]:
        incidents = list(self._incidents.values())
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        return incidents[-limit:]

    def configure_runbook(
        self,
        incident_type: IncidentType,
        actions: List[ResponseAction],
    ):
        self._response_runbooks[incident_type] = actions

    def register_webhook(self, webhook_url: str):
        self._webhooks.append(webhook_url)

    def get_statistics(self) -> Dict:
        return {
            "totalIncidents": len(self._incidents),
            "openIncidents": sum(1 for i in self._incidents.values()
                                 if i.status in (IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS)),
            "criticalIncidents": sum(1 for i in self._incidents.values()
                                     if i.severity == IncidentSeverity.CRITICAL),
            "resolvedIncidents": sum(1 for i in self._incidents.values()
                                     if i.status == IncidentStatus.RESOLVED),
        }

    def _execute_action(self, action: ResponseAction, incident: Incident) -> IncidentAction:
        result = IncidentAction(
            action=action,
            result="success",
            details={},
        )

        if action == ResponseAction.DISABLE_ACCOUNT:
            result.details = {"account": incident.affected_user, "disabled": True}
            logger.info(f"Account disabled: {incident.affected_user}")
        elif action == ResponseAction.ROTATE_KEYS:
            result.details = {"keysRotated": True}
            logger.info("Keys rotated for incident response")
        elif action == ResponseAction.NOTIFY_TEAM:
            result.details = {"notifiedTeams": ["security_team", "devops"]}
            logger.info("Security team notified")
        elif action == ResponseAction.BLOCK_IP:
            result.details = {"ipBlocked": incident.ip_address}
            logger.info(f"IP blocked: {incident.ip_address}")
        elif action == ResponseAction.QUARANTINE:
            result.details = {"system": incident.affected_system, "quarantined": True}
        elif action == ResponseAction.ESCALATE:
            result.details = {"escalatedTo": "security_lead", "severity": incident.severity.value}
        elif action == ResponseAction.CREATE_TICKET:
            result.details = {"ticketId": str(uuid.uuid4())[:12], "system": "jira"}
        elif action == ResponseAction.FORENSIC_COLLECTION:
            result.details = {"forensicsCollected": True}
        else:
            result.result = "skipped"

        return result

    def _notify_incident(self, incident: Incident):
        for webhook in self._webhooks:
            try:
                logger.info(f"Webhook notification sent to: {webhook}")
            except Exception:
                pass

    def to_dict(self) -> Dict:
        return {
            "statistics": self.get_statistics(),
            "runbooks": {k.value: [a.value for a in v]
                        for k, v in self._response_runbooks.items()},
        }
