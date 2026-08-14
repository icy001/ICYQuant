"""Control authorization: decision, grant and governance adapter (Commit 29 Part 1.2 §3-12, §20).

The Control Plane only understands three outcomes — ALLOW / DENY /
REQUIRE_APPROVAL — and never reasons about roles, policies or approval
rules itself (§3). Those belong to Governance.

Every ALLOW produces a time-bound ``AuthorizationGrant`` bound to the
command fingerprint. The executor must present a valid grant before it
may touch a handler, so a command cannot be mutated between
authorization and execution (§8-10, §20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol

from .command import ControlCommand, command_fingerprint
from .context import ControlAuthorizationContext


class AuthorizationEffect(str, Enum):
    """The three outcomes the Control Plane recognises (§5)."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class AuthorizationDecision:
    """Governance's verdict expressed in control-plane terms (§5).

    ``reason_code`` is a stable, machine-readable code; ``reason`` is the
    human-readable explanation surfaced in results and audit events.
    """

    effect: AuthorizationEffect
    reason: str = ""
    decision_id: str | None = None
    reason_code: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def allow(
        cls,
        reason: str = "allowed",
        *,
        decision_id: str | None = None,
        reason_code: str = "GOV_ALLOWED",
        expires_at: datetime | None = None,
    ) -> "AuthorizationDecision":
        return cls(
            effect=AuthorizationEffect.ALLOW,
            reason=reason,
            decision_id=decision_id,
            reason_code=reason_code,
            expires_at=expires_at,
        )

    @classmethod
    def deny(
        cls,
        reason: str = "denied",
        *,
        decision_id: str | None = None,
        reason_code: str = "GOV_DENIED",
    ) -> "AuthorizationDecision":
        return cls(
            effect=AuthorizationEffect.DENY,
            reason=reason,
            decision_id=decision_id,
            reason_code=reason_code,
        )

    @classmethod
    def require_approval(
        cls,
        reason: str = "approval required",
        *,
        decision_id: str | None = None,
        reason_code: str = "GOV_APPROVAL_REQUIRED",
        expires_at: datetime | None = None,
    ) -> "AuthorizationDecision":
        return cls(
            effect=AuthorizationEffect.REQUIRE_APPROVAL,
            reason=reason,
            decision_id=decision_id,
            reason_code=reason_code,
            expires_at=expires_at,
        )

    def is_allowed(self) -> bool:
        return self.effect is AuthorizationEffect.ALLOW

    def is_denied(self) -> bool:
        return self.effect is AuthorizationEffect.DENY

    def requires_approval(self) -> bool:
        return self.effect is AuthorizationEffect.REQUIRE_APPROVAL


class ControlAuthorizer(Protocol):
    """Unified authorization boundary (§3).

    The Control Plane does not care how roles, policies, approvals or
    quorum are computed — Governance does. It only consumes the three
    outcomes ALLOW / DENY / REQUIRE_APPROVAL.
    """

    def authorize(
        self, context: ControlAuthorizationContext
    ) -> AuthorizationDecision: ...


@dataclass(frozen=True)
class AuthorizationGrant:
    """Time-bound proof that a specific command was authorised (§8).

    The grant is bound to the command fingerprint (§10), so swapping
    ``trading:pause`` for ``trading:kill`` — or mutating the target from
    ``oms-primary`` to ``oms-secondary`` — invalidates the grant (§22-23).
    """

    grant_id: str
    decision_id: str | None
    request_id: str
    command_id: str
    principal_id: str
    resource: str
    action: str
    granted_at: datetime
    fingerprint: str
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or datetime.now(timezone.utc)) >= self.expires_at


class GrantValidator:
    """Validates a grant against the command about to be executed (§11).

    Every check that fails means the command that will actually run is not
    the command that was authorised — the Control Plane fails closed.
    """

    def validate(self, grant: AuthorizationGrant, command: ControlCommand) -> bool:
        if grant.command_id != command.command_id:
            return False
        if grant.resource != command.resource:
            return False
        if grant.action != command.action:
            return False
        if command_fingerprint(command) != grant.fingerprint:
            return False
        return True

    def is_expired(
        self, grant: AuthorizationGrant, now: datetime | None = None
    ) -> bool:
        return grant.is_expired(now)


class GovernanceAuthorizer:
    """Adapter from Governance to the Control Plane (§4).

    Maps a ``ControlAuthorizationContext`` onto a GovernanceContext and
    translates the governance ``GovernanceDecision`` (ALLOW / DENY /
    REQUIRE_APPROVAL) into an ``AuthorizationDecision``. Role resolution
    is delegated to an injected ``role_resolver`` so the adapter stays
    free of governance policy internals.
    """

    def __init__(
        self,
        governance: Any,
        *,
        role_resolver: Callable[[str], tuple[str, ...] | list[str]] | None = None,
        environment: str | None = None,
        severity: str | None = None,
    ) -> None:
        self.governance = governance
        self._role_resolver = role_resolver or (lambda principal_id: ())
        self._environment = environment
        self._severity = severity

    def authorize(
        self, context: ControlAuthorizationContext
    ) -> AuthorizationDecision:
        decision = self.governance.evaluate(self._to_governance_context(context))
        return self._map(decision)

    def _to_governance_context(self, context: ControlAuthorizationContext) -> Any:
        from .target import ControlTarget  # local import: avoids a cycle

        from services.governance.decision import GovernanceContext

        target = context.target
        if not isinstance(target, ControlTarget):
            environment = self._environment or "production"
        else:
            environment = self._environment or target.environment

        parameters = context.parameters or {}
        severity = self._severity or parameters.get("severity")

        return GovernanceContext(
            principal_id=context.principal_id,
            role_ids=tuple(self._role_resolver(context.principal_id)),
            resource=context.resource,
            action=context.action,
            environment=environment,
            severity=severity,
        )

    def _map(self, decision: Any) -> AuthorizationDecision:
        effect = getattr(decision, "effect", None)
        effect_value = getattr(effect, "value", effect)
        reason = getattr(decision, "reason", "") or ""
        decision_id = getattr(decision, "decision_id", None)
        reason_code = getattr(decision, "reason_code", None) or None

        if effect_value == "ALLOW":
            return AuthorizationDecision.allow(
                reason=reason,
                decision_id=decision_id,
                reason_code=reason_code or "GOV_ALLOWED",
            )
        if effect_value == "REQUIRE_APPROVAL":
            return AuthorizationDecision.require_approval(
                reason=reason,
                decision_id=decision_id,
                reason_code=reason_code or "GOV_APPROVAL_REQUIRED",
            )
        return AuthorizationDecision.deny(
            reason=reason,
            decision_id=decision_id,
            reason_code=reason_code or "GOV_DENIED",
        )
