"""
ICYQuant Security API Endpoints

REST API for security operations: status, audit, key rotation,
compliance checks, and governance.
"""

from __future__ import annotations

from typing import Dict, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional as OptionalType

from services.security.service import SecurityService
from services.security.audit_center import AuditAction, AuditSeverity
from services.security.compliance import ComplianceFramework
from services.security.governance import GovernanceCategory, RiskLevel
from services.security.policy_engine import PolicyEffect

router = APIRouter(prefix="/api/v1/security", tags=["Security"])

_security_service: Optional[SecurityService] = None


def get_security_service() -> SecurityService:
    global _security_service
    if _security_service is None:
        _security_service = SecurityService()
    return _security_service


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: OptionalType[str] = None


class LoginResponse(BaseModel):
    session_id: str
    access_token: str
    refresh_token: str


class KeyRotationRequest(BaseModel):
    policy_name: str
    force: bool = False


class ComplianceCheckRequest(BaseModel):
    frameworks: OptionalType[List[str]] = None


class GovernanceSubmitRequest(BaseModel):
    title: str
    category: str
    requested_by: str
    risk_level: str = "low"
    description: str = ""
    approvers: OptionalType[List[str]] = None


class GovernanceActionRequest(BaseModel):
    approver: str
    comment: str = ""


@router.get("/status")
async def get_security_status(
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Get overall security platform status."""
    return svc.get_status()


@router.post("/login")
async def login(
    request: LoginRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Authenticate user."""
    try:
        session = svc.authenticate(
            username=request.username,
            password=request.password,
            mfa_code=request.mfa_code,
        )
        tokens = session.tokens
        access_token = next((t for t in tokens if t.token_type.value == "access"), None)
        refresh_token = next((t for t in tokens if t.token_type.value == "refresh"), None)

        return {
            "sessionId": session.id,
            "accessToken": access_token.token_value if access_token else "",
            "refreshToken": refresh_token.token_value if refresh_token else "",
            "expiresAt": access_token.expires_at.isoformat() if access_token else "",
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/audit")
async def get_audit_log(
    actor: OptionalType[str] = None,
    action: OptionalType[str] = None,
    severity: OptionalType[str] = None,
    trace_id: OptionalType[str] = None,
    limit: int = 100,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Query audit logs with filters."""
    action_enum = AuditAction(action) if action else None
    severity_enum = AuditSeverity(severity) if severity else None

    entries = svc.audit.query(
        actor=actor,
        action=action_enum,
        severity=severity_enum,
        trace_id=trace_id,
        limit=limit,
    )

    return {
        "total": len(entries),
        "entries": [e.to_dict() for e in entries],
    }


@router.post("/rotate-key")
async def rotate_key(
    request: KeyRotationRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Execute key rotation for a given policy."""
    try:
        plan = svc.key_rotation.execute_rotation(request.policy_name)
        svc.audit.log(
            action=AuditAction.KEY_ROTATION,
            actor="system",
            target=request.policy_name,
            severity=AuditSeverity.HIGH,
            details={"force": request.force, "planId": plan.id},
        )
        return plan.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance")
async def run_compliance_check(
    request: ComplianceCheckRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Run compliance checks for specified frameworks."""
    frameworks = None
    if request.frameworks:
        frameworks = [ComplianceFramework(f) for f in request.frameworks]

    report = svc.compliance.generate_report(frameworks)
    return report.to_dict()


@router.post("/governance/submit")
async def submit_governance_request(
    request: GovernanceSubmitRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Submit a governance approval request."""
    try:
        request_obj = svc.governance.submit_request(
            title=request.title,
            category=GovernanceCategory(request.category),
            requested_by=request.requested_by,
            risk_level=RiskLevel(request.risk_level),
            description=request.description,
            approvers=request.approvers,
        )
        return request_obj.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/governance/{request_id}/approve")
async def approve_governance_request(
    request_id: str,
    body: GovernanceActionRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Approve a governance request."""
    try:
        svc.governance.approve_request(request_id, body.approver, body.comment)
        req = svc.governance.get_request(request_id)
        return req.to_dict() if req else {}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/governance/{request_id}/reject")
async def reject_governance_request(
    request_id: str,
    body: GovernanceActionRequest,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Reject a governance request."""
    try:
        svc.governance.reject_request(request_id, body.approver, body.comment)
        req = svc.governance.get_request(request_id)
        return req.to_dict() if req else {}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/governance/requests")
async def list_governance_requests(
    status: OptionalType[str] = None,
    category: OptionalType[str] = None,
    limit: int = 50,
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """List governance approval requests."""
    from services.security.governance import ApprovalStatus
    status_enum = ApprovalStatus(status) if status else None
    category_enum = GovernanceCategory(category) if category else None

    requests = svc.governance.list_requests(
        status=status_enum,
        category=category_enum,
        limit=limit,
    )
    return {
        "total": len(requests),
        "requests": [r.to_dict() for r in requests],
    }


@router.get("/policies")
async def list_policies(
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """List all security policies."""
    return {
        "policies": svc.policy_engine.list_policies(),
    }


@router.get("/audit/integrity")
async def verify_audit_integrity(
    svc: SecurityService = Depends(get_security_service),
) -> Dict:
    """Verify audit log integrity."""
    return svc.audit.verify_integrity()
