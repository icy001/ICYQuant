"""Control plane interfaces and facade (Commit 29 Part 1.1 §20-25, §22-23, §42).

* ``ControlHandler`` — unified interface every control handler implements.
* ``ControlAuthorizer`` — the Governance integration boundary. The Control
  Plane does not own Policy / Role / Permission / Approval Rule; those belong
  to Governance (§26). It only accepts AUTHORIZED or REJECTED (§24-25).
* ``ControlPlane`` — facade and single entry point. ``submit`` runs the
  production pipeline::

      validation -> target resolution -> idempotency -> authorization
      -> dispatch -> registry -> handler -> executor -> target service

  Governance authorization is inserted at the boundary; in the Part 1.1
  skeleton it is optional so the foundation can be exercised standalone.
"""

from __future__ import annotations

from typing import Protocol

from .command import ControlCommand, command_fingerprint
from .dispatcher import ControlDispatcher
from .errors import ControlExecutionError
from .executor import ControlExecutor
from .registry import ControlRegistry, IdempotencyRegistry
from .request import ControlRequest, validate_request
from .result import ControlResult
from .target import TargetResolver


class ControlHandler(Protocol):
    """Unified control handler interface (§20)."""

    def execute(self, command: ControlCommand) -> ControlResult: ...


class ControlAuthorizer(Protocol):
    """Governance integration boundary (§25).

    Implementations raise ``UnauthorizedControl`` to reject a request (fail
    closed); a return value means the request is authorised.
    """

    def authorize(self, request: ControlRequest) -> None: ...


class ControlPlane:
    """Production control plane facade (§22-23)."""

    def __init__(
        self,
        registry: ControlRegistry,
        dispatcher: ControlDispatcher,
        executor: ControlExecutor,
        *,
        authorizer: ControlAuthorizer | None = None,
        target_resolver: TargetResolver | None = None,
        idempotency_registry: IdempotencyRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.dispatcher = dispatcher
        self.executor = executor
        self.authorizer = authorizer
        self.target_resolver = target_resolver
        self.idempotency = idempotency_registry or IdempotencyRegistry()

    def submit(self, request: ControlRequest) -> ControlResult:
        # 1. Request validation — missing critical fields are rejected and
        #    never reach the dispatcher (§32).
        validate_request(request)

        # 2. Target resolution — fail closed (§34-35).
        if self.target_resolver is not None:
            self.target_resolver.resolve(request.command.target)

        # 3. Idempotency — same key + same fingerprint returns the previous
        #    result; same key + different fingerprint is a conflict (§27-30).
        fingerprint = command_fingerprint(request.command)
        cached = self.idempotency.get(request.idempotency_key)
        if cached is not None:
            return self.idempotency.put(
                request.idempotency_key, fingerprint, cached
            )

        # 4. Governance authorization boundary (§24-26). The Control Plane
        #    does not own policy; it only accepts AUTHORIZED / REJECTED.
        if self.authorizer is not None:
            self.authorizer.authorize(request)

        # 5. Dispatch through the registry (§18).
        handler = self.dispatcher.dispatch(request.command)

        # 6. Execute the already-authorised command (§17, §19).
        try:
            result = self.executor.execute(request.command, handler)
        except ControlExecutionError:
            raise
        except Exception as exc:
            raise ControlExecutionError(
                f"control handler failed for {request.command.resource}:"
                f"{request.command.action}: {exc}"
            ) from exc

        # 7. Record the result so resubmission is idempotent.
        return self.idempotency.put(request.idempotency_key, fingerprint, result)
