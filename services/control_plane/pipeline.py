"""Governed command authorization pipeline (Commit 29 Part 1.2 §6-17).

The pipeline is the single path a control request may take:

    Request -> Validation -> Authorization -> Approval Gate -> Dispatch
             -> Executor (grant-guarded)

Safety invariants (§34):

1. Executor can never be reached without authorization.
2. DENY never reaches the Dispatcher.
3. REQUIRE_APPROVAL never reaches the Executor.
4. Every execution requires an ``AuthorizationGrant``.
5. The grant is bound to the command fingerprint.
6. The grant is time-bound.
7. Target mutation is rejected (fingerprint mismatch).
8. Idempotency conflicts are rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .audit import ControlAuditEventType
from .authorizer import (
    AuthorizationDecision,
    AuthorizationGrant,
    ControlAuthorizer,
    GrantValidator,
)
from .command import command_fingerprint
from .context import ControlAuthorizationContext
from .dispatcher import ControlDispatcher
from .errors import (
    AuthorizationExpired,
    ControlExecutionError,
    ControlPlaneError,
    UnauthorizedControl,
)
from .executor import ControlExecutor
from .request import ControlRequest, validate_request
from .result import ControlResult


class ControlPipeline:
    """The governed execution pipeline (§6).

    ``process`` authorises a request end-to-end. ``submit_with_grant`` is
    the approval-completed path: Governance has already produced a final
    decision and an ``AuthorizationGrant``, so the pipeline may safely
    dispatch and execute without re-authorising (§14-15).
    """

    def __init__(
        self,
        authorizer: ControlAuthorizer,
        dispatcher: ControlDispatcher,
        executor: ControlExecutor,
        *,
        grant_validator: GrantValidator | None = None,
        idempotency: Any | None = None,
        audit_log: Any | None = None,
        grant_factory: Any | None = None,
    ) -> None:
        self.authorizer = authorizer
        self.dispatcher = dispatcher
        self.executor = executor
        self.grant_validator = grant_validator or GrantValidator()
        self.idempotency = idempotency
        self.audit_log = audit_log
        self._grant_factory = grant_factory
        self._grant_sequence = 0

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def process(self, request: ControlRequest) -> ControlResult:
        """Full governed path: validate -> authorise -> dispatch -> execute (§6)."""
        validate_request(request)
        context = ControlAuthorizationContext.from_request(request)
        self._record(
            ControlAuditEventType.AUTHORIZATION_REQUESTED, request, context
        )

        if self.idempotency is not None:
            cached = self.idempotency.get(request.idempotency_key)
            if cached is not None:
                return self.idempotency.put(
                    request.idempotency_key,
                    command_fingerprint(request.command),
                    cached,
                )

        decision = self.authorizer.authorize(context)

        if decision.is_denied():
            self._record(
                ControlAuditEventType.AUTHORIZATION_DENIED,
                request,
                context,
                decision,
            )
            return self._rejected(request, decision)

        if decision.requires_approval():
            self._record(
                ControlAuditEventType.APPROVAL_REQUIRED,
                request,
                context,
                decision,
            )
            return self._pending_approval(request, decision)

        grant = self._create_grant(request, decision)
        self._record(
            ControlAuditEventType.AUTHORIZATION_GRANT_CREATED,
            request,
            context,
            decision,
            grant,
        )
        self._record(
            ControlAuditEventType.AUTHORIZATION_GRANTED,
            request,
            context,
            decision,
            grant,
        )

        result = self._dispatch_and_execute(request, grant)

        if self.idempotency is not None:
            self.idempotency.put(
                request.idempotency_key,
                command_fingerprint(request.command),
                result,
            )
        return result

    def submit_with_grant(
        self, request: ControlRequest, grant: AuthorizationGrant
    ) -> ControlResult:
        """Approval-completed path (§14-15).

        Called only after Governance has completed approval (quorum met)
        and produced an ``AuthorizationGrant``. The pipeline re-validates
        the grant against the command before anything is dispatched, so an
        invalid or expired grant can never execute.
        """
        validate_request(request)
        if self.grant_validator.is_expired(grant):
            raise AuthorizationExpired(
                "authorization grant expired for command "
                f"{request.command.command_id}"
            )
        if not self.grant_validator.validate(grant, request.command):
            raise UnauthorizedControl(
                "invalid authorization grant for command "
                f"{request.command.command_id}"
            )
        return self._dispatch_and_execute(request, grant)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _dispatch_and_execute(
        self, request: ControlRequest, grant: AuthorizationGrant
    ) -> ControlResult:
        handler = self.dispatcher.dispatch(request.command)
        self._record(
            ControlAuditEventType.EXECUTION_STARTED,
            request,
            grant=grant,
        )
        try:
            result = self.executor.execute(
                request.command,
                handler,
                grant,
            )
        except ControlPlaneError:
            self._record(
                ControlAuditEventType.EXECUTION_FAILED,
                request,
                grant=grant,
            )
            raise
        except Exception as exc:
            self._record(
                ControlAuditEventType.EXECUTION_FAILED,
                request,
                grant=grant,
            )
            raise ControlExecutionError(
                f"control handler failed for command "
                f"{request.command.command_id}: {exc}"
            ) from exc
        self._record(
            ControlAuditEventType.EXECUTION_SUCCEEDED,
            request,
            grant=grant,
        )
        return result

    def _create_grant(
        self,
        request: ControlRequest,
        decision: AuthorizationDecision,
    ) -> AuthorizationGrant:
        if self._grant_factory is not None:
            grant = self._grant_factory(request, decision)
            if grant is not None:
                return grant
        self._grant_sequence += 1
        now = datetime.now(timezone.utc)
        return AuthorizationGrant(
            grant_id=f"GRANT-{self._grant_sequence:06d}",
            decision_id=decision.decision_id,
            request_id=request.request_id,
            command_id=request.command.command_id,
            principal_id=request.command.requested_by,
            resource=request.command.resource,
            action=request.command.action,
            granted_at=now,
            fingerprint=command_fingerprint(request.command),
            expires_at=decision.expires_at,
        )

    def _rejected(
        self,
        request: ControlRequest,
        decision: AuthorizationDecision,
    ) -> ControlResult:
        return ControlResult(
            command_id=request.command.command_id,
            state="REJECTED",
            success=False,
            error_code=decision.reason_code or "GOVERNANCE_DENIED",
            error_message=decision.reason or "governance denied the control command",
        )

    def _pending_approval(
        self,
        request: ControlRequest,
        decision: AuthorizationDecision,
    ) -> ControlResult:
        return ControlResult(
            command_id=request.command.command_id,
            state="WAITING_APPROVAL",
            success=False,
            error_code=decision.reason_code or "APPROVAL_REQUIRED",
            error_message=decision.reason or "approval required before execution",
        )

    def _record(
        self,
        event_type: ControlAuditEventType,
        request: ControlRequest,
        context: ControlAuthorizationContext | None = None,
        decision: AuthorizationDecision | None = None,
        grant: AuthorizationGrant | None = None,
    ) -> None:
        if self.audit_log is None:
            return
        detail: dict[str, Any] = {}
        if context is not None:
            detail["principal_id"] = context.principal_id
        if decision is not None:
            detail["effect"] = decision.effect.value
            detail["reason"] = decision.reason
            if decision.decision_id is not None:
                detail["decision_id"] = decision.decision_id
            if decision.reason_code is not None:
                detail["reason_code"] = decision.reason_code
        if grant is not None:
            detail["grant_id"] = grant.grant_id
        self.audit_log.record(
            event_type,
            correlation_id=request.command.correlation_id,
            request_id=request.request_id,
            command_id=request.command.command_id,
            detail=detail or None,
        )
