"""
Emergency Controller — executes emergency governance actions.

Part 1.5: the Emergency Controller is a policy-constrained authority
that can freeze, cancel, reduce, and revoke during critical events.

Key principle:
    Emergency authority can ONLY reduce/contain risk, NEVER increase it.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .emergency_state import EmergencyState, EmergencyStateType
from .emergency_action import EmergencyAction, EmergencyActionType
from .emergency_policy import EmergencyPolicy, STANDARD_EMERGENCY_POLICY
from .control_state import GovernanceStateType


class EmergencyController:
    """Executes emergency governance actions under policy constraints.

    Not a "super-admin" — operates under a strict EmergencyPolicy that:
      - Only allows risk-reducing actions
      - Has scope and duration limits
      - Requires full audit
    """

    def __init__(self, policy: Optional[EmergencyPolicy] = None):
        self._policy = policy or STANDARD_EMERGENCY_POLICY
        self._state = EmergencyState()
        self._actions: List[EmergencyAction] = []
        self._escalation_level: int = 0

        # Injected dependencies
        self._freeze_controller: Any = None
        self._exposure_controller: Any = None
        self._revoke_controller: Any = None
        self._escalation_controller: Any = None
        self._audit_engine: Any = None

    @property
    def is_active(self) -> bool:
        return self._state.is_active

    @property
    def current_state(self) -> EmergencyStateType:
        return self._state.state

    def set_freeze_controller(self, ctrl: Any) -> None:
        self._freeze_controller = ctrl

    def set_exposure_controller(self, ctrl: Any) -> None:
        self._exposure_controller = ctrl

    def set_revoke_controller(self, ctrl: Any) -> None:
        self._revoke_controller = ctrl

    def set_escalation_controller(self, ctrl: Any) -> None:
        self._escalation_controller = ctrl

    def set_audit_engine(self, engine: Any) -> None:
        self._audit_engine = engine

    # ── Activation ──

    def activate(
        self,
        reason: str = "",
        trigger: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Activate emergency mode.

        Returns:
            Dict with activation status and allowed actions.
        """
        if self._state.is_active:
            return {"status": "ALREADY_ACTIVE", "state": self._state.to_dict()}

        self._state.activate(
            trigger=trigger,
            description=reason,
            correlation_id=correlation_id,
        )

        # Audit
        self._audit_activation(reason, correlation_id)

        return {
            "status": "ACTIVATED",
            "state": self._state.to_dict(),
            "allowed_actions": [a.name for a in self._policy.allowed_actions],
            "max_duration_seconds": self._policy.max_duration_seconds,
        }

    def deactivate(self, reason: str = "") -> Dict[str, Any]:
        """Deactivate emergency mode."""
        if not self._state.is_active:
            return {"status": "NOT_ACTIVE"}

        self._state.resolve()
        self._escalation_level = 0

        return {
            "status": "RESOLVED",
            "reason": reason,
            "duration_seconds": self._state.duration_seconds,
            "actions_taken": len(self._actions),
        }

    # ── Emergency Actions ──

    def freeze_all(
        self,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Issue a global new-risk freeze."""
        return self._execute_action(
            EmergencyActionType.FREEZE_ALL,
            target="GLOBAL",
            reason=reason,
            correlation_id=correlation_id,
        )

    def freeze_strategy(
        self,
        strategy_id: str,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Freeze a specific strategy."""
        return self._execute_action(
            EmergencyActionType.FREEZE_STRATEGY,
            target=strategy_id,
            reason=reason,
            correlation_id=correlation_id,
        )

    def cancel_all_orders(
        self,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Cancel all pending orders."""
        return self._execute_action(
            EmergencyActionType.CANCEL_ALL_ORDERS,
            target="GLOBAL",
            reason=reason,
            correlation_id=correlation_id,
        )

    def reduce_exposure(
        self,
        target_pct: float = 0.10,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Force reduce portfolio exposure."""
        return self._execute_action(
            EmergencyActionType.REDUCE_EXPOSURE,
            target=f"EXPOSURE:{target_pct}",
            reason=reason,
            correlation_id=correlation_id,
        )

    def revoke_authority(
        self,
        authority_id: str,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Revoke a specific authority."""
        return self._execute_action(
            EmergencyActionType.REVOKE_AUTHORITY,
            target=authority_id,
            reason=reason,
            correlation_id=correlation_id,
        )

    def escalate(
        self,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Escalate to human operators."""
        self._escalation_level += 1
        self._state.escalate(reason)
        return self._execute_action(
            EmergencyActionType.ESCALATE,
            target=f"LEVEL:{self._escalation_level}",
            reason=reason,
            correlation_id=correlation_id,
        )

    # ── Internal ──

    def _execute_action(
        self,
        action_type: EmergencyActionType,
        target: str,
        reason: str,
        correlation_id: str,
    ) -> Dict[str, Any]:
        """Execute an emergency action with policy checks."""
        # Check policy
        if not self._policy.is_allowed(action_type):
            return {
                "status": "FORBIDDEN",
                "action": action_type.name,
                "reason": f"Action {action_type.name} is not allowed by emergency policy {self._policy.policy_id}.",
            }

        # Check emergency is active
        if not self._state.is_active:
            return {
                "status": "EMERGENCY_NOT_ACTIVE",
                "action": action_type.name,
                "reason": "Emergency mode is not active.",
            }

        # Create action record
        action = EmergencyAction(
            action_type=action_type,
            target=target,
            reason=reason,
            correlation_id=correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}",
        )

        # Attempt execution via controllers
        result = self._do_execute(action)
        action.mark_executed(result)
        self._actions.append(action)

        # Audit
        self._audit_action(action)

        return {
            "status": "EXECUTED",
            "action": action_type.name,
            "target": target,
            "result": result,
        }

    def _do_execute(self, action: EmergencyAction) -> Dict[str, Any]:
        """Route action to the appropriate controller."""
        action_type = action.action_type

        if action_type == EmergencyActionType.FREEZE_ALL:
            if self._freeze_controller:
                return self._freeze_controller.freeze(
                    scope="GLOBAL",
                    reason=action.reason,
                    correlation_id=action.correlation_id,
                )
            return {"status": "NO_OP", "reason": "FreezeController not available."}

        elif action_type == EmergencyActionType.CANCEL_ALL_ORDERS:
            if self._freeze_controller:
                return self._freeze_controller.cancel_pending(
                    reason=action.reason,
                    correlation_id=action.correlation_id,
                )
            return {"status": "NO_OP", "reason": "FreezeController not available."}

        elif action_type == EmergencyActionType.REDUCE_EXPOSURE:
            if self._exposure_controller:
                return self._exposure_controller.reduce_exposure(
                    reason=action.reason,
                    correlation_id=action.correlation_id,
                )
            return {"status": "NO_OP", "reason": "ExposureController not available."}

        elif action_type == EmergencyActionType.REVOKE_AUTHORITY:
            if self._revoke_controller:
                return self._revoke_controller.revoke(
                    target=action.target,
                    reason=action.reason,
                    correlation_id=action.correlation_id,
                )
            return {"status": "NO_OP", "reason": "RevokeController not available."}

        elif action_type == EmergencyActionType.ESCALATE:
            if self._escalation_controller:
                return self._escalation_controller.escalate(
                    decision=None,
                    reason=action.reason,
                    level=self._escalation_level,
                )
            return {"status": "ESCALATED", "level": self._escalation_level}

        else:
            return {"status": "NOT_IMPLEMENTED", "action": action_type.name}

    def _audit_activation(self, reason: str, correlation_id: str) -> None:
        if not self._audit_engine:
            return
        try:
            self._audit_engine.record_event(
                event_type=None,
                entity_type="EMERGENCY",
                entity_id=self._state.correlation_id or "EMERGENCY-001",
                actor=None,
                action=None,
                outcome=None,
                reason=reason,
                correlation_id=correlation_id,
            )
        except Exception:
            pass

    def _audit_action(self, action: EmergencyAction) -> None:
        if not self._audit_engine:
            return
        try:
            self._audit_engine.record_event(
                event_type=None,
                entity_type="EMERGENCY_ACTION",
                entity_id=action.action_id,
                actor=None,
                action=None,
                outcome=None,
                reason=action.reason,
                correlation_id=action.correlation_id,
            )
        except Exception:
            pass

    def get_state(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def get_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in reversed(self._actions[-limit:])]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "escalation_level": self._escalation_level,
            "actions_taken": len(self._actions),
            "duration_seconds": self._state.duration_seconds if self.is_active else 0.0,
            "policy": self._policy.to_dict(),
        }
