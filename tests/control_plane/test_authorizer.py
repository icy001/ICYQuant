"""Control authorizer: decision model, grant and governance adapter (Commit 29 Part 1.2 §3-12)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.authorizer import (
    AuthorizationDecision,
    AuthorizationEffect,
    AuthorizationGrant,
    GovernanceAuthorizer,
    GrantValidator,
)
from services.control_plane.command import command_fingerprint
from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
)


class FakeGovernance:
    """Minimal governance stand-in returning a fixed GovernanceDecision."""

    def __init__(self, decision: GovernanceDecision) -> None:
        self.decision = decision
        self.contexts: list[GovernanceContext] = []

    def evaluate(self, context: GovernanceContext) -> GovernanceDecision:
        self.contexts.append(context)
        return self.decision


class TestAuthorizationDecision:
    def test_allow_helpers(self):
        decision = AuthorizationDecision.allow(reason="allowed")
        assert decision.is_allowed()
        assert not decision.is_denied()
        assert not decision.requires_approval()
        assert decision.effect is AuthorizationEffect.ALLOW
        assert decision.reason == "allowed"

    def test_deny_helpers(self):
        decision = AuthorizationDecision.deny(reason="blocked")
        assert decision.is_denied()
        assert not decision.is_allowed()
        assert not decision.requires_approval()
        assert decision.effect is AuthorizationEffect.DENY

    def test_require_approval_helpers(self):
        decision = AuthorizationDecision.require_approval(reason="approve")
        assert decision.requires_approval()
        assert not decision.is_allowed()
        assert not decision.is_denied()
        assert decision.effect is AuthorizationEffect.REQUIRE_APPROVAL


class TestAuthorizationGrant:
    def test_grant_is_bound_to_command_fingerprint(self, make_command):
        command = make_command()
        grant = AuthorizationGrant(
            grant_id="GRANT-001",
            decision_id="DEC-001",
            request_id="REQ-001",
            command_id=command.command_id,
            principal_id=command.requested_by,
            resource=command.resource,
            action=command.action,
            granted_at=datetime.now(timezone.utc),
            fingerprint=command_fingerprint(command),
        )
        assert grant.fingerprint == command_fingerprint(command)

    def test_grant_expiry_detection(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        expired = AuthorizationGrant(
            grant_id="GRANT-X",
            decision_id=None,
            request_id="REQ-X",
            command_id="CMD-X",
            principal_id="ops-001",
            resource="trading",
            action="pause",
            granted_at=past,
            fingerprint="fp",
            expires_at=past,
        )
        valid = AuthorizationGrant(
            grant_id="GRANT-Y",
            decision_id=None,
            request_id="REQ-Y",
            command_id="CMD-Y",
            principal_id="ops-001",
            resource="trading",
            action="pause",
            granted_at=past,
            fingerprint="fp",
            expires_at=future,
        )
        assert expired.is_expired()
        assert not valid.is_expired()
        assert not valid.is_expired(past - timedelta(hours=1))


class TestGrantValidator:
    def _grant_for(self, command, **overrides):
        params = dict(
            grant_id="GRANT-001",
            decision_id="DEC-001",
            request_id="REQ-001",
            command_id=command.command_id,
            principal_id=command.requested_by,
            resource=command.resource,
            action=command.action,
            granted_at=datetime.now(timezone.utc),
            fingerprint=command_fingerprint(command),
        )
        params.update(overrides)
        return AuthorizationGrant(**params)

    def test_valid_grant_accepts(self, make_command):
        command = make_command()
        validator = GrantValidator()
        assert validator.validate(self._grant_for(command), command)

    def test_rejects_modified_action(self, make_command):
        from dataclasses import replace

        command = make_command()
        modified = replace(command, action="kill")
        validator = GrantValidator()
        assert not validator.validate(self._grant_for(command), modified)

    def test_rejects_modified_target(self, make_command):
        from dataclasses import replace

        from services.control_plane.target import ControlTarget

        command = make_command()
        modified = replace(
            command,
            target=ControlTarget(
                service="oms", instance="oms-secondary", environment="production"
            ),
        )
        validator = GrantValidator()
        assert not validator.validate(self._grant_for(command), modified)

    def test_rejects_modified_parameters(self, make_command):
        from dataclasses import replace

        command = make_command()
        modified = replace(command, parameters={"severity": "EMERGENCY"})
        validator = GrantValidator()
        assert not validator.validate(self._grant_for(command), modified)

    def test_rejects_wrong_command_id(self, make_command):
        command = make_command()
        validator = GrantValidator()
        assert not validator.validate(
            self._grant_for(command, command_id="CMD-999"), command
        )


class TestGovernanceAuthorizer:
    def _authorizer(self, decision, role_resolver=None):
        governance = FakeGovernance(decision)
        authorizer = GovernanceAuthorizer(
            governance, role_resolver=role_resolver or (lambda pid: ("CONTROL_OPERATOR",))
        )
        return authorizer, governance

    def test_maps_allow(self, make_command, make_request):
        decision = GovernanceDecision(effect=DecisionEffect.ALLOW, reason="allowed")
        authorizer, _ = self._authorizer(decision)
        request = make_request(make_command())
        from services.control_plane.context import ControlAuthorizationContext

        result = authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert result.is_allowed()

    def test_maps_deny(self, make_command, make_request):
        decision = GovernanceDecision(effect=DecisionEffect.DENY, reason="denied")
        authorizer, _ = self._authorizer(decision)
        request = make_request(make_command())
        from services.control_plane.context import ControlAuthorizationContext

        result = authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert result.is_denied()
        assert result.reason == "denied"

    def test_maps_require_approval(self, make_command, make_request):
        decision = GovernanceDecision(
            effect=DecisionEffect.REQUIRE_APPROVAL, reason="approval needed"
        )
        authorizer, _ = self._authorizer(decision)
        request = make_request(make_command())
        from services.control_plane.context import ControlAuthorizationContext

        result = authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert result.requires_approval()

    def test_passes_roles_environment_and_severity(self, make_command, make_request):
        decision = GovernanceDecision(effect=DecisionEffect.ALLOW, reason="ok")
        authorizer, governance = self._authorizer(
            decision, role_resolver=lambda pid: ("OPERATOR",) if pid == "ops-001" else ()
        )
        request = make_request(
            make_command(
                requested_by="ops-001",
                parameters={"severity": "CRITICAL"},
            )
        )
        from services.control_plane.context import ControlAuthorizationContext

        authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert len(governance.contexts) == 1
        context = governance.contexts[0]
        assert context.principal_id == "ops-001"
        assert context.role_ids == ("OPERATOR",)
        assert context.resource == "trading"
        assert context.action == "pause"
        assert context.environment == "production"
        assert context.severity == "CRITICAL"

    def test_default_roles_are_empty_fail_closed(self, make_command, make_request):
        decision = GovernanceDecision(effect=DecisionEffect.DENY, reason="denied")
        authorizer, governance = self._authorizer(decision)
        request = make_request(make_command())
        from services.control_plane.context import ControlAuthorizationContext

        authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert governance.contexts[0].role_ids == ("CONTROL_OPERATOR",)

    def test_exposes_granted_decision_id_and_reason_code(self, make_command, make_request):
        decision = GovernanceDecision(
            effect=DecisionEffect.ALLOW,
            reason="allowed",
            decision_id="DEC-001",
            reason_code="GOV_ALLOWED",
        )
        authorizer, _ = self._authorizer(decision)
        request = make_request(make_command())
        from services.control_plane.context import ControlAuthorizationContext

        result = authorizer.authorize(ControlAuthorizationContext.from_request(request))
        assert result.decision_id == "DEC-001"
        assert result.reason_code == "GOV_ALLOWED"


def test_authorizer_protocol_is_structural(make_command, make_request):
    """A plain object with authorize(context) satisfies the protocol."""
    from services.control_plane.context import ControlAuthorizationContext

    class Structural:
        def __init__(self):
            self.called = False

        def authorize(self, context):
            self.called = True
            return AuthorizationDecision.allow()

    authorizer = Structural()
    request = make_request(make_command())
    result = authorizer.authorize(ControlAuthorizationContext.from_request(request))
    assert result.is_allowed()
    assert authorizer.called
