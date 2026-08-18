"""
Dashboard authentication & RBAC.

The Dashboard reuses the official security platform:

- AuthenticationService  -> credentials + access tokens
- AuthorizationService   -> roles + permission grants
- AuditCenter            -> tamper-evident audit trail

It never bypasses Backend authorization: every Dashboard endpoint
goes through token validation plus role enforcement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.security.audit_center import AuditAction, AuditCenter, AuditSeverity
from services.security.authentication import AuthenticationService, TokenType
from services.security.authorization import (
    AuthorizationService,
    Permission,
    PermissionGrant,
    ResourceType,
    Role,
)

logger = logging.getLogger(__name__)

# Dashboard role label -> Backend role id
ROLE_MAP: Dict[str, str] = {
    "ADMIN": "admin",
    "TRADER": "trader",
    "RISK": "risk_manager",
    "OPERATOR": "ops",
    "RESEARCHER": "researcher",
    "READ_ONLY": "read_only",
}

# Seed users: (username, password, dashboard role)
SEED_USERS: List[tuple[str, str, str]] = [
    ("admin", "admin123", "ADMIN"),
    ("trader", "trader123", "TRADER"),
    ("risk", "risk123", "RISK"),
    ("operator", "operator123", "OPERATOR"),
    ("researcher", "researcher123", "RESEARCHER"),
    ("readonly", "readonly123", "READ_ONLY"),
]

_READ_ONLY_GRANTS: List[PermissionGrant] = [
    PermissionGrant(resource=ResourceType.TRADE, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.ORDER, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.POSITION, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.RISK, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.PORTFOLIO, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.STRATEGY, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.SYSTEM, permissions={Permission.READ}),
    PermissionGrant(resource=ResourceType.AUDIT_LOG, permissions={Permission.READ}),
]


@dataclass
class Principal:
    """Authenticated Dashboard principal."""

    token: str
    user_id: str
    username: str
    role: str  # dashboard role label (ADMIN / TRADER / ...)
    backend_role: str  # backend role id


class DashboardAuth:
    """Auth façade shared by all Dashboard endpoints."""

    def __init__(self) -> None:
        self.authentication = AuthenticationService()
        self.authorization = AuthorizationService()
        self.audit = AuditCenter()
        self._user_ids: Dict[str, str] = {}  # username -> user id
        self._usernames: Dict[str, str] = {}  # user id -> username
        self._roles: Dict[str, str] = {}  # user id -> dashboard role label
        self._seeded = False

    def seed(self) -> None:
        """Register seed users and bind roles (idempotent)."""
        if self._seeded:
            return
        if self.authorization.get_role("read_only") is None:
            self.authorization.create_role(
                Role(
                    id="read_only",
                    name="Read Only",
                    description="Read-only Dashboard access",
                    grants=list(_READ_ONLY_GRANTS),
                )
            )
        for username, password, role in SEED_USERS:
            existing = getattr(self.authentication, "_users", {}).get(username)
            if existing is not None:
                user = existing
            else:
                user = self.authentication.register_user(
                    username=username,
                    email=f"{username}@icyquant.local",
                    password=password,
                )
            self.authorization.assign_role(user.id, ROLE_MAP[role])
            self._user_ids[username] = user.id
            self._usernames[user.id] = username
            self._roles[user.id] = role
        self._seeded = True
        logger.info("Dashboard auth seeded with %d users", len(SEED_USERS))

    def login(self, username: str, password: str, ip_address: str = "") -> dict:
        """Validate credentials, return access token + user profile."""
        try:
            session = self.authentication.authenticate(
                username, password, ip_address=ip_address
            )
        except Exception as exc:  # noqa: BLE001 - surface official auth error
            self.audit.log(
                action=AuditAction.LOGIN,
                actor=username,
                severity=AuditSeverity.WARNING,
                details={"result": "failed", "error": str(exc)},
                ip_address=ip_address,
            )
            raise
        token = next(
            (t for t in session.tokens if t.token_type == TokenType.ACCESS), None
        )
        if token is None:
            raise RuntimeError("authentication did not issue an access token")
        role = self._roles.get(session.user_id, "")
        self.audit.log(
            action=AuditAction.LOGIN,
            actor=username,
            severity=AuditSeverity.INFO,
            details={"result": "success", "role": role},
            ip_address=ip_address,
        )
        return {
            "token": token.token_value,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "user": {"username": username, "role": role},
        }

    def logout(self, principal: "Principal", ip_address: str = "") -> None:
        token = self.authentication.validate_token(principal.token)
        if token is not None:
            self.authentication.revoke_token(token.id)
        self.audit.log(
            action=AuditAction.LOGOUT,
            actor=principal.username,
            severity=AuditSeverity.INFO,
            ip_address=ip_address,
        )

    def resolve(self, token_value: str) -> Optional["Principal"]:
        """Resolve a bearer token into a Principal (None when invalid)."""
        token = self.authentication.validate_token(token_value)
        if token is None:
            return None
        username = self._usernames.get(token.user_id)
        role = self._roles.get(token.user_id)
        if not username or not role:
            return None
        return Principal(
            token=token_value,
            user_id=token.user_id,
            username=username,
            role=role,
            backend_role=ROLE_MAP.get(role, role),
        )

    def record(
        self,
        action: AuditAction,
        principal: "Principal",
        target: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        details: Optional[dict] = None,
        ip_address: str = "",
    ) -> None:
        """Write an audit entry on behalf of a principal."""
        self.audit.log(
            action=action,
            actor=principal.username,
            target=target,
            severity=severity,
            details=details or {},
            ip_address=ip_address,
        )


auth = DashboardAuth()

_bearer = HTTPBearer(auto_error=False)


def _resolve_principal(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Principal:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    principal = auth.resolve(credentials.credentials)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_roles(*roles: str) -> Callable:
    """FastAPI dependency enforcing authentication (+ optional roles).

    Usage::

        @router.get("/overview")
        def overview(p: Principal = Depends(require_roles())):
            ...

        @router.post("/orders/{id}/cancel")
        def cancel(p: Principal = Depends(require_roles("TRADER", "ADMIN"))):
            ...
    """

    def dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    ) -> Principal:
        principal = _resolve_principal(credentials)
        if roles and principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role(s): {', '.join(roles)}",
            )
        return principal

    return dependency


__all__ = [
    "Principal",
    "DashboardAuth",
    "auth",
    "require_roles",
    "ROLE_MAP",
]
