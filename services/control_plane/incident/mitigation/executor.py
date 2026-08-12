"""
MitigationExecutor / Registry / Engine — dispatch control actions through
adapter executors.

The Control Plane never mutates Position / OMS / Execution directly: every
control action is dispatched through a registered executor adapter, which is
the only place that knows the downstream system's internals
(spec section 11/13/14/16).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..audit.event_type import IncidentAuditEventType
from .action import MitigationAction
from .action_type import MitigationActionType
from .result import MitigationResult


class MitigationExecutor(ABC):
    """Adapter interface for executing one control action."""

    @abstractmethod
    def execute(
        self,
        action: MitigationAction,
    ) -> MitigationResult:
        raise NotImplementedError


class MitigationExecutorRegistry:
    """action_type → executor mapping. Production code must not grow
    ``if action_type == ...`` chains — new actions are adapters (spec 13)."""

    def __init__(self) -> None:
        self._executors: dict[MitigationActionType, MitigationExecutor] = {}

    def register(
        self,
        action_type: MitigationActionType,
        executor: MitigationExecutor,
    ) -> None:
        self._executors[action_type] = executor

    def get(self, action_type: MitigationActionType) -> MitigationExecutor:
        executor = self._executors.get(action_type)
        if executor is None:
            raise KeyError(
                f"no executor registered for {action_type.value}"
            )
        return executor

    def __contains__(self, action_type: MitigationActionType) -> bool:
        return action_type in self._executors

    def __len__(self) -> int:
        return len(self._executors)


class MitigationEngine:
    """Executes a MitigationPlan through the executor registry.

    Safety properties (spec section 15/16/19):

      * every action is dispatched through a registered executor — the engine
        never touches Position / OMS / Execution directly;
      * idempotency: the same (incident, action_type, version) is executed at
        most once; retries return the previous result;
      * fail_fast: a failed action stops the plan unless the plan explicitly
        runs in best-effort mode.
    """

    def __init__(
        self,
        registry: MitigationExecutorRegistry,
        audit_service: Any | None = None,
    ) -> None:
        self.registry = registry
        self.audit_service = audit_service
        self._results: dict[str, MitigationResult] = {}

    def execute(
        self,
        plan,
        *,
        actor: str = "system",
    ) -> list[MitigationResult]:
        results: list[MitigationResult] = []

        for action in plan.actions:
            key = action.idempotency_key

            # Idempotency: never re-execute a control action.
            if key in self._results:
                results.append(self._results[key])
                continue

            if self.audit_service is not None:
                self.audit_service.record(
                    action.incident_id,
                    IncidentAuditEventType.MITIGATION_STARTED,
                    actor=actor,
                    payload={
                        "action_type": action.action_type.value,
                        "requested_by": action.requested_by,
                    },
                    action_id=action.action_id,
                )

            executor = self.registry.get(action.action_type)
            result = executor.execute(action)

            self._results[key] = result
            results.append(result)

            if self.audit_service is not None:
                self.audit_service.record(
                    action.incident_id,
                    (
                        IncidentAuditEventType.MITIGATION_COMPLETED
                        if result.success
                        else IncidentAuditEventType.MITIGATION_FAILED
                    ),
                    actor=actor,
                    payload={
                        "action_type": action.action_type.value,
                        "message": result.message,
                        "external_reference": result.external_reference,
                    },
                    action_id=action.action_id,
                )

            if not result.success and plan.fail_fast:
                break

        return results
