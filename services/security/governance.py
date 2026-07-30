"""
ICYQuant Governance Center

Unified governance for data, AI, models, security, and policy.
Supports approval workflows: Policy -> Review -> Approve -> Deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class GovernanceCategory(str, Enum):
    DATA = "data"
    AI_MODEL = "ai_model"
    SECURITY = "security"
    POLICY = "policy"
    ACCESS = "access"
    COMPLIANCE = "compliance"
    DEPLOYMENT = "deployment"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DEPLOYED = "deployed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: GovernanceCategory = GovernanceCategory.POLICY
    title: str = ""
    description: str = ""
    requested_by: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    status: ApprovalStatus = ApprovalStatus.DRAFT
    approvers: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    approvals: List[Dict] = field(default_factory=list)
    rejections: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    attachments: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def approve(self, approver: str, comment: str = ""):
        self.approvals.append({
            "approver": approver,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
        if self._all_approved():
            self.status = ApprovalStatus.APPROVED

    def reject(self, approver: str, comment: str = ""):
        self.rejections.append({
            "approver": approver,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        })
        self.status = ApprovalStatus.REJECTED
        self.updated_at = datetime.now()

    def submit(self):
        self.status = ApprovalStatus.SUBMITTED
        self.updated_at = datetime.now()

    def escalate(self, reason: str):
        self.status = ApprovalStatus.ESCALATED
        self.updated_at = datetime.now()

    def _all_approved(self) -> bool:
        if not self.approvers:
            return True
        approved_by = {a["approver"] for a in self.approvals}
        return approved_by.issubset(set(self.approvers)) and len(approved_by) >= 1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "requestedBy": self.requested_by,
            "riskLevel": self.risk_level.value,
            "status": self.status.value,
            "approvers": self.approvers,
            "assignedTo": self.assigned_to,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "dueDate": self.due_date.isoformat() if self.due_date else None,
        }


@dataclass
class GovernancePolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: GovernanceCategory = GovernanceCategory.POLICY
    description: str = ""
    requires_approval: bool = True
    approvers: List[str] = field(default_factory=list)
    risk_threshold: RiskLevel = RiskLevel.MEDIUM
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "requiresApproval": self.requires_approval,
            "approvers": self.approvers,
            "riskThreshold": self.risk_threshold.value,
            "enabled": self.enabled,
        }


class GovernanceCenter:
    """
    Unified governance center.

    Manages approval workflows for data, AI, security, policy,
    and deployment changes. Implements Policy -> Review -> Approve -> Deploy.
    """

    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._policies: Dict[str, GovernancePolicy] = {}
        self._audit_log: List[Dict] = []

        self._init_default_policies()

    def _init_default_policies(self):
        defaults = [
            GovernancePolicy(
                name="AI Model Deployment",
                category=GovernanceCategory.AI_MODEL,
                description="Approval required for AI model deployment",
                requires_approval=True,
                approvers=["ai_lead", "risk_manager"],
                risk_threshold=RiskLevel.MEDIUM,
            ),
            GovernancePolicy(
                name="Policy Changes",
                category=GovernanceCategory.POLICY,
                description="Security policy changes require approval",
                requires_approval=True,
                approvers=["security_lead", "compliance_officer"],
                risk_threshold=RiskLevel.HIGH,
            ),
            GovernancePolicy(
                name="Data Access",
                category=GovernanceCategory.DATA,
                description="Sensitive data access requires approval",
                requires_approval=True,
                approvers=["data_owner"],
                risk_threshold=RiskLevel.MEDIUM,
            ),
            GovernancePolicy(
                name="Production Deployment",
                category=GovernanceCategory.DEPLOYMENT,
                description="Production deployments require approval",
                requires_approval=True,
                approvers=["tech_lead", "devops_lead"],
                risk_threshold=RiskLevel.HIGH,
            ),
            GovernancePolicy(
                name="Privilege Escalation",
                category=GovernanceCategory.ACCESS,
                description="Privilege escalation requires multi-party approval",
                requires_approval=True,
                approvers=["security_lead", "admin"],
                risk_threshold=RiskLevel.CRITICAL,
            ),
        ]
        for p in defaults:
            self._policies[p.name] = p

    def submit_request(
        self,
        title: str,
        category: GovernanceCategory,
        requested_by: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        description: str = "",
        approvers: Optional[List[str]] = None,
        due_date: Optional[datetime] = None,
    ) -> ApprovalRequest:
        policy = self._match_policy(category, risk_level)
        effective_approvers = approvers or (policy.approvers if policy else [])

        request = ApprovalRequest(
            category=category,
            title=title,
            description=description,
            requested_by=requested_by,
            risk_level=risk_level,
            approvers=effective_approvers,
            due_date=due_date,
        )

        if not policy or not policy.requires_approval or risk_level == RiskLevel.LOW:
            request.status = ApprovalStatus.APPROVED
            request.approvals.append({
                "approver": "auto",
                "comment": "Auto-approved (low risk or no policy)",
                "timestamp": datetime.now().isoformat(),
            })
        else:
            request.submit()

        self._requests[request.id] = request
        self._audit("submit", request.id, requested_by)
        logger.info(f"Governance request submitted: {title} (risk: {risk_level.value})")
        return request

    def approve_request(self, request_id: str, approver: str, comment: str = ""):
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request '{request_id}' not found")
        request.approve(approver, comment)
        self._audit("approve", request_id, approver)

    def reject_request(self, request_id: str, approver: str, comment: str = ""):
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request '{request_id}' not found")
        request.reject(approver, comment)
        self._audit("reject", request_id, approver)

    def escalate_request(self, request_id: str, reason: str = ""):
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request '{request_id}' not found")
        request.escalate(reason)

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def list_requests(
        self,
        status: Optional[ApprovalStatus] = None,
        category: Optional[GovernanceCategory] = None,
        limit: int = 50,
    ) -> List[ApprovalRequest]:
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r.status == status]
        if category:
            requests = [r for r in requests if r.category == category]
        return requests[-limit:]

    def list_policies(self) -> List[Dict]:
        return [p.to_dict() for p in self._policies.values()]

    def create_policy(self, policy: GovernancePolicy) -> GovernancePolicy:
        self._policies[policy.name] = policy
        return policy

    def _match_policy(self, category: GovernanceCategory, risk: RiskLevel) -> Optional[GovernancePolicy]:
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if policy.category != category:
                continue
            if risk_order.get(risk, 0) <= risk_order.get(policy.risk_threshold, 0):
                return policy
        return None

    def _audit(self, action: str, request_id: str, actor: str):
        self._audit_log.append({
            "action": action,
            "requestId": request_id,
            "actor": actor,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict:
        return {
            "totalRequests": len(self._requests),
            "pendingRequests": sum(1 for r in self._requests.values()
                                   if r.status in (ApprovalStatus.SUBMITTED, ApprovalStatus.IN_REVIEW)),
            "approvedRequests": sum(1 for r in self._requests.values() if r.status == ApprovalStatus.APPROVED),
            "rejectedRequests": sum(1 for r in self._requests.values() if r.status == ApprovalStatus.REJECTED),
            "governancePolicies": len(self._policies),
        }
