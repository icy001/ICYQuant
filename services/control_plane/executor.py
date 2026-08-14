"""Control command executor boundary (Commit 29 Part 1.1 §17, §19; Part 1.2 §20-21).

The executor does not decide whether an operation is permitted. It only runs
commands that have already been authorised by Governance::

    Control Plane -> Registry -> Handler -> Target Service

It never contains branches like ``if action == "pause": oms.pause()`` — that
would turn the Control Plane into a God Service (§19).

Part 1.2 adds the executor guard (Layer 5 of defense in depth, §20-21):
every execution must present a valid, unexpired ``AuthorizationGrant``
bound to the exact command fingerprint. A missing or invalid grant raises
``UnauthorizedControl``; an expired grant raises ``AuthorizationExpired``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authorizer import AuthorizationGrant, GrantValidator
from .errors import AuthorizationExpired, UnauthorizedControl


class ControlExecutor:
    """Executes an already-authorised command through its registered handler.

    ``grant`` is optional only for backwards compatibility with the Part 1.1
    skeleton. The governed pipeline always passes a grant, so in production
    every execution is guarded (§20).

    Part 1.4 adds the ownership guard (§27): an execution is only allowed
    when it holds the current, unexpired ``ExecutionClaim`` with a fencing
    token at least the one currently issued (``can_execute``). Authorization
    + Ownership + Fingerprint must all hold before a command runs (§27).
    """

    def __init__(
        self,
        grant_validator: GrantValidator | None = None,
        claim_store: Any | None = None,
    ) -> None:
        self.grant_validator = grant_validator or GrantValidator()
        self.claim_store = claim_store

    def execute(
        self,
        command: Any,
        handler: Any,
        grant: AuthorizationGrant | None = None,
    ) -> Any:
        if grant is not None:
            if self.grant_validator.is_expired(grant):
                raise AuthorizationExpired(
                    f"authorization grant expired for command {command.command_id}"
                )
            if not self.grant_validator.validate(grant, command):
                raise UnauthorizedControl(
                    "invalid authorization grant for command "
                    f"{command.command_id}"
                )
        return handler.execute(command)

    def can_execute(
        self,
        claim: Any,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Ownership guard (§22, §27, §52): current, unexpired fencing token only.

        A stale claim from a zombie worker — a lower fencing token than the
        one currently issued — can never execute, and an expired lease can
        never execute (§22, §25).
        """
        if claim is None:
            return False
        reference = now or datetime.now(timezone.utc)
        expires_at = getattr(claim, "expires_at", None)
        if expires_at is not None and expires_at <= reference:
            return False
        if self.claim_store is not None:
            current = self.claim_store.current_fencing_token(
                getattr(claim, "command_id", "")
            )
            if claim.fencing_token < current:
                return False
        return True
