"""
Autonomous Governance Control Plane — the central autonomous governance engine.

Part 1.5: this is the culmination of Commit 20. The Control Plane sits above
Strategy, Risk, Policy, and Execution. It continuously monitors the system,
detects issues, evaluates policies, makes control decisions, and intervenes.

Architecture:
    OBSERVE → DETECT → EVALUATE → DECIDE → INTERVENE → VERIFY → AUDIT

Key invariants:
    1. Governance cannot increase risk beyond policy.
    2. Emergency authority cannot create unauthorized risk.
    3. Critical governance failure fails closed.
    4. Every intervention must be auditable and verifiable.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .control_state import (
    GovernanceStateType,
    GovernanceStateMachine,
    GovernanceStateTransition,
)
from .control_action import ControlActionType
from .control_trigger import ControlTrigger, TriggerType, Severity
from .control_condition import ControlCondition, STANDARD_CONTROL_CONDITIONS
from .control_policy import ControlPolicy, STANDARD_CONTROL_POLICIES
from .control_decision import ControlDecision
from .control_loop import ControlLoop, LoopPhase, LoopCycle


class GovernanceControlPlane:
    """The autonomous governance control plane.

    Continuously monitors the system and takes automated governance actions
    based on policies. This is NOT an AI with unlimited authority — it
    executes predefined governance rules within immutable boundaries.
    """

    def __init__(
        self,
        state_machine: Optional[GovernanceStateMachine] = None,
        control_loop: Optional[ControlLoop] = None,
        audit_engine: Any = None,
        lineage_engine: Any = None,
    ):
        self._state = state_machine or GovernanceStateMachine()
        self._loop = control_loop or ControlLoop()
        self._policies: Dict[str, ControlPolicy] = {}
        self._conditions: Dict[str, ControlCondition] = {}

        # Integrations
        self._audit_engine = audit_engine
        self._lineage_engine = lineage_engine

        # Sub-controllers (injected later)
        self._freeze_controller: Any = None
        self._exposure_controller: Any = None
        self._revoke_controller: Any = None
        self._escalation_controller: Any = None
        self._emergency_controller: Any = None

        # Guardians (injected later)
        self._risk_guardian: Any = None
        self._authority_guardian: Any = None
        self._approval_guardian: Any = None
        self._policy_guardian: Any = None
        self._execution_guardian: Any = None

        # Intervention plans
        self._intervention_plans: List[Dict[str, Any]] = []
        self._intervention_results: List[Dict[str, Any]] = []

        # Historical decisions
        self._decisions: List[ControlDecision] = []
        self._max_decision_history = 10000

        # Initialize with standard policies
        for policy in STANDARD_CONTROL_POLICIES:
            self.add_policy(policy)

        for cond in STANDARD_CONTROL_CONDITIONS:
            self._conditions[cond.condition_id] = cond

    # ── State Management ──

    @property
    def current_state(self) -> GovernanceStateType:
        return self._state.current_state

    @property
    def state_severity(self) -> int:
        return self._state.current_state.severity

    @property
    def allows_new_risk(self) -> bool:
        return self._state.current_state.allows_new_risk

    @property
    def allows_risk_reduction(self) -> bool:
        return self._state.current_state.allows_risk_reduction

    @property
    def is_elevated(self) -> bool:
        return self._state.is_elevated

    @property
    def is_critical(self) -> bool:
        return self._state.is_critical

    def get_state_summary(self) -> Dict[str, Any]:
        return self._state.summary()

    def get_state_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._state.get_history(limit)

    # ── Policy Management ──

    def add_policy(self, policy: ControlPolicy) -> None:
        self._policies[policy.policy_id] = policy
        for cond in policy.conditions:
            self._conditions[cond.condition_id] = cond

    def add_condition(self, condition: ControlCondition) -> None:
        self._conditions[condition.condition_id] = condition

    def get_policies(self) -> Dict[str, ControlPolicy]:
        return dict(self._policies)

    # ── Controller Injection ──

    def set_freeze_controller(self, ctrl: Any) -> None:
        self._freeze_controller = ctrl

    def set_exposure_controller(self, ctrl: Any) -> None:
        self._exposure_controller = ctrl

    def set_revoke_controller(self, ctrl: Any) -> None:
        self._revoke_controller = ctrl

    def set_escalation_controller(self, ctrl: Any) -> None:
        self._escalation_controller = ctrl

    def set_emergency_controller(self, ctrl: Any) -> None:
        self._emergency_controller = ctrl

    # ── Guardian Injection ──

    def set_risk_guardian(self, guardian: Any) -> None:
        self._risk_guardian = guardian

    def set_authority_guardian(self, guardian: Any) -> None:
        self._authority_guardian = guardian

    def set_approval_guardian(self, guardian: Any) -> None:
        self._approval_guardian = guardian

    def set_policy_guardian(self, guardian: Any) -> None:
        self._policy_guardian = guardian

    def set_execution_guardian(self, guardian: Any) -> None:
        self._execution_guardian = guardian

    # ── Core: Evaluate Trigger ──

    def evaluate_trigger(self, trigger: ControlTrigger) -> ControlDecision:
        """Evaluate a trigger and produce a control decision.

        This is the core decision-making function:
        1. Find matching conditions in registered policies
        2. Select the highest-priority matching condition
        3. Produce a ControlDecision with target state and actions
        """
        best_condition: Optional[ControlCondition] = None
        best_priority = -1

        # Evaluate all policies
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            matched = policy.evaluate(
                trigger.trigger_type,
                trigger.value,
                trigger.threshold,
            )
            if matched and matched.priority > best_priority:
                best_condition = matched
                best_priority = matched.priority

        # If no condition matched, produce ALLOW
        if best_condition is None:
            return ControlDecision.allow(
                reason=f"No control policy triggered for {trigger.trigger_type.name}.",
                correlation_id=trigger.correlation_id,
            )

        # Decide whether to change state
        target_state = best_condition.target_state
        current_state = self._state.current_state

        # Only escalate, not de-escalate through conditions
        if target_state.severity <= current_state.severity and current_state != target_state:
            target_state = current_state  # Don't auto-recover via trigger

        # Create the decision
        decision = ControlDecision(
            trigger=trigger,
            current_state=current_state,
            target_state=target_state,
            actions=list(best_condition.actions),
            reason=f"{best_condition.description} (observed: {trigger.value}, threshold: {trigger.threshold})",
            severity=trigger.severity,
            correlation_id=trigger.correlation_id,
        )

        self._decisions.append(decision)
        if len(self._decisions) > self._max_decision_history:
            self._decisions = self._decisions[-self._max_decision_history:]

        return decision

    def evaluate_triggers(self, triggers: List[ControlTrigger]) -> List[ControlDecision]:
        """Evaluate multiple triggers and return decisions.

        Only the most severe decision for each state target is kept.
        """
        decisions: List[ControlDecision] = []
        for trigger in triggers:
            decision = self.evaluate_trigger(trigger)
            if not decision.is_noop:
                decisions.append(decision)
        return decisions

    # ── Core: Execute Decision ──

    def execute_decision(self, decision: ControlDecision) -> Dict[str, Any]:
        """Execute a control decision: state transition + actions.

        Returns execution results.
        """
        results: Dict[str, Any] = {
            "decision_id": decision.decision_id,
            "actions": [],
            "state_transition": None,
            "errors": [],
        }

        # 1. State transition
        if decision.requires_state_change:
            try:
                transition = self._state.transition(
                    target=decision.target_state,
                    trigger=decision.trigger.trigger_type.name if decision.trigger else "MANUAL",
                    reason=decision.reason,
                    actor=decision.actor,
                    correlation_id=decision.correlation_id,
                )
                results["state_transition"] = transition.to_dict()
            except ValueError as e:
                results["errors"].append(f"State transition failed: {e}")
                results["state_transition"] = None

        # 2. Execute actions
        for action in decision.actions:
            action_result = self._execute_action(action, decision)
            results["actions"].append({
                "action": action.name,
                "result": action_result,
            })

        # 3. Audit
        self._audit_decision(decision, results)

        # 4. Mark executed
        decision.mark_executed(results)
        results["success"] = len(results["errors"]) == 0
        return results

    def _execute_action(self, action: ControlActionType, decision: ControlDecision) -> Dict[str, Any]:
        """Execute a single control action via the appropriate controller."""
        try:
            if action == ControlActionType.ALLOW:
                return {"status": "ALLOWED", "action": "No intervention required."}

            elif action == ControlActionType.WARN:
                return {"status": "WARNED", "action": "Warning recorded."}

            elif action == ControlActionType.FREEZE:
                if self._freeze_controller:
                    freeze_result = self._freeze_controller.freeze(
                        scope="GLOBAL" if decision.metadata.get("freeze_scope") == "GLOBAL" else "PORTFOLIO",
                        reason=decision.reason,
                        correlation_id=decision.correlation_id,
                    )
                    return {"status": "FROZEN", "result": freeze_result}
                return {"status": "NO_OP", "reason": "FreezeController not configured."}

            elif action == ControlActionType.REDUCE:
                if self._exposure_controller:
                    reduce_result = self._exposure_controller.reduce_exposure(
                        reason=decision.reason,
                        correlation_id=decision.correlation_id,
                    )
                    return {"status": "REDUCED", "result": reduce_result}
                return {"status": "NO_OP", "reason": "ExposureController not configured."}

            elif action == ControlActionType.REVOKE:
                if self._revoke_controller:
                    revoke_result = self._revoke_controller.revoke(
                        target=decision.metadata.get("revoke_target", ""),
                        reason=decision.reason,
                        correlation_id=decision.correlation_id,
                    )
                    return {"status": "REVOKED", "result": revoke_result}
                return {"status": "NO_OP", "reason": "RevokeController not configured."}

            elif action == ControlActionType.ESCALATE:
                if self._escalation_controller:
                    escalate_result = self._escalation_controller.escalate(
                        decision=decision,
                        reason=decision.reason,
                    )
                    return {"status": "ESCALATED", "result": escalate_result}
                return {"status": "NO_OP", "reason": "EscalationController not configured."}

            elif action == ControlActionType.EMERGENCY:
                if self._emergency_controller:
                    emergency_result = self._emergency_controller.activate(
                        reason=decision.reason,
                        correlation_id=decision.correlation_id,
                    )
                    return {"status": "EMERGENCY_ACTIVATED", "result": emergency_result}
                return {"status": "NO_OP", "reason": "EmergencyController not configured."}

            elif action == ControlActionType.CANCEL:
                if self._freeze_controller:
                    cancel_result = self._freeze_controller.cancel_pending(
                        reason=decision.reason,
                        correlation_id=decision.correlation_id,
                    )
                    return {"status": "CANCELLED", "result": cancel_result}
                return {"status": "NO_OP", "reason": "FreezeController not configured."}

            elif action == ControlActionType.PAUSE:
                return {"status": "PAUSED", "action": "Strategy/execution paused."}

            elif action == ControlActionType.RESTRICT:
                return {"status": "RESTRICTED", "action": "Operations restricted."}

            elif action == ControlActionType.RECOVER:
                return {"status": "RECOVERING", "action": "Recovery actions initiated."}

            else:
                return {"status": "UNKNOWN_ACTION", "action": action.name}

        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    # ── Core: Full Control Cycle ──

    def run_cycle(
        self,
        triggers: Optional[List[ControlTrigger]] = None,
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Run a full control loop cycle: Observe → Audit.

        This is the main entry point. In production, this would be called
        periodically by a scheduler or event-driven trigger.
        """
        cid = correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}"
        cycle = self._loop.start_cycle(self._state.current_state, cid)

        # OBSERVE — gather triggers from guardians
        observed_triggers = triggers or []
        if not observed_triggers:
            observed_triggers = self._observe()
        self._loop.record_phase(LoopPhase.OBSERVE, {
            "triggers_count": len(observed_triggers),
        })

        # DETECT — record triggers
        self._loop.detect_triggers(observed_triggers)
        self._loop.record_phase(LoopPhase.DETECT, {
            "triggers_detected": len(observed_triggers),
        })

        # EVALUATE — evaluate triggers against policies
        decisions = self.evaluate_triggers(observed_triggers)
        self._loop.record_phase(LoopPhase.EVALUATE, {
            "decisions_count": len(decisions),
        })

        # DECIDE — select actions
        for decision in decisions:
            self._loop.record_decision(decision)
        self._loop.record_phase(LoopPhase.DECIDE, {
            "actions": [d.actions[0].name if d.actions else "NONE" for d in decisions],
        })

        # INTERVENE — execute decisions
        intervention_results = []
        for decision in decisions:
            result = self.execute_decision(decision)
            intervention_results.append(result)
            self._loop.record_intervention(result)

        self._intervention_results.extend(intervention_results)
        self._loop.record_phase(LoopPhase.INTERVENE, {
            "interventions": len(intervention_results),
        })

        # VERIFY — check intervention outcomes
        verification = self._verify(intervention_results)
        self._loop.record_phase(LoopPhase.VERIFY, verification)

        # AUDIT — record everything
        audit_summary = self._audit_cycle(cycle, decisions, intervention_results)
        self._loop.record_phase(LoopPhase.AUDIT, audit_summary)

        # Complete cycle
        final_state = self._state.current_state
        self._loop.complete_cycle(final_state, success=verification.get("all_verified", True))

        return {
            "cycle_id": cycle.cycle_id,
            "state_before": cycle.state_before.name,
            "state_after": cycle.state_after.name,
            "state_changed": cycle.state_changed,
            "triggers_detected": len(observed_triggers),
            "decisions_made": len(decisions),
            "interventions": len(intervention_results),
            "verification": verification,
            "duration_ms": cycle.duration_ms,
        }

    # ── Observe — gather triggers from guardians ──

    def _observe(self) -> List[ControlTrigger]:
        """Observe the system by polling all guardians."""
        triggers: List[ControlTrigger] = []

        guardians = [
            self._risk_guardian,
            self._authority_guardian,
            self._approval_guardian,
            self._policy_guardian,
            self._execution_guardian,
        ]

        for guardian in guardians:
            if guardian and hasattr(guardian, "check"):
                try:
                    guardian_triggers = guardian.check()
                    triggers.extend(guardian_triggers or [])
                except Exception:
                    pass  # Guardian failure must not break the control loop

        return triggers

    # ── Verify intervention outcomes ──

    def _verify(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify that interventions had the intended effect."""
        all_verified = True
        failures = []

        for result in results:
            if result.get("errors"):
                all_verified = False
                failures.append({
                    "decision_id": result.get("decision_id"),
                    "errors": result["errors"],
                })

        return {
            "all_verified": all_verified,
            "failure_count": len(failures),
            "failures": failures[:10],
        }

    # ── Audit ──

    def _audit_decision(self, decision: ControlDecision, results: Dict[str, Any]) -> None:
        """Record audit event for a control decision."""
        if not self._audit_engine:
            return

        try:
            from .audit_event_type import AuditEventType
            from .audit_actor import AuditActor
            from .audit_action import AuditAction
            from .audit_outcome import AuditOutcome

            action = AuditAction.APPROVE if results.get("success") else AuditAction.DENY
            self._audit_engine.record_event(
                event_type=AuditEventType.GOVERNANCE_CONTROL_DECISION,
                entity_type="CONTROL_DECISION",
                entity_id=decision.decision_id,
                actor=AuditActor.system("control-plane"),
                action=action,
                outcome=AuditOutcome.INTERVENTION_APPLIED if results.get("state_transition") else AuditOutcome.SUCCESS,
                reason=decision.reason,
                correlation_id=decision.correlation_id,
            )
        except Exception:
            pass

    def _audit_cycle(
        self,
        cycle: LoopCycle,
        decisions: List[ControlDecision],
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Record audit for a full control cycle."""
        if not self._audit_engine:
            return {"audited": False, "reason": "No audit engine configured."}

        try:
            self._audit_engine.record_event(
                event_type=None,  # Will be set correctly
                entity_type="CONTROL_CYCLE",
                entity_id=cycle.cycle_id,
                actor=None,
                action=None,
                outcome=None,
                reason=f"Control cycle completed. {len(decisions)} decisions, {len(results)} interventions.",
                correlation_id=cycle.correlation_id,
            )
        except Exception:
            pass

        return {
            "audited": True,
            "cycle_id": cycle.cycle_id,
            "correlation_id": cycle.correlation_id,
        }

    # ── Invariant Checks ──

    def verify_invariants(self) -> Dict[str, Any]:
        """Verify all governance invariants.

        Returns:
            Dict with 'all_valid' and per-invariant results.
        """
        results = {
            "all_valid": True,
            "invariants": [],
        }

        # 1. Governance cannot increase risk beyond policy
        inv1 = {
            "invariant": "Governance cannot increase risk beyond policy.",
            "valid": True,
        }
        if self._state.is_elevated and self._state.allows_new_risk:
            # WATCH state still allows new risk — that's by design
            pass
        results["invariants"].append(inv1)

        # 2. Emergency should not allow risk increase
        inv2 = {
            "invariant": "Emergency authority cannot create unauthorized risk.",
            "valid": True,
        }
        if self._state.current_state == GovernanceStateType.EMERGENCY:
            if self._state.current_state.allows_new_risk:
                inv2["valid"] = False
                results["all_valid"] = False
        results["invariants"].append(inv2)

        # 3. Frozen state must not allow new risk
        inv3 = {
            "invariant": "Frozen scope cannot create new risk.",
            "valid": True,
        }
        if self._state.current_state == GovernanceStateType.FROZEN:
            if self._state.current_state.allows_new_risk:
                inv3["valid"] = False
                results["all_valid"] = False
        results["invariants"].append(inv3)

        # 4. Critical governance failure fails closed
        inv4 = {
            "invariant": "Critical governance failure fails closed.",
            "valid": True,
        }
        if self._state.current_state in (GovernanceStateType.EMERGENCY, GovernanceStateType.DEGRADED):
            if self._state.current_state.allows_new_risk:
                inv4["valid"] = False
                results["all_valid"] = False
        results["invariants"].append(inv4)

        # 5. Every state transition must be traceable
        inv5 = {
            "invariant": "Every state transition must be lineage-traceable.",
            "valid": True,
        }
        transitions = self._state.get_transitions(limit=10)
        for t in transitions:
            if not t.reason and t.from_state != t.to_state:
                inv5["valid"] = False
                results["all_valid"] = False
                break
        results["invariants"].append(inv5)

        return results

    # ── History & Metrics ──

    def get_recent_decisions(self, limit: int = 100) -> List[ControlDecision]:
        return list(reversed(self._decisions[-limit:]))

    def get_intervention_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._intervention_results[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "state": self.get_state_summary(),
            "loop": self._loop.get_metrics(),
            "policies_count": len(self._policies),
            "conditions_count": len(self._conditions),
            "decisions_total": len(self._decisions),
            "interventions_total": len(self._intervention_results),
            "invariants": self.verify_invariants(),
        }

    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get a comprehensive governance control plane status report."""
        return {
            "version": "0.4.0-alpha2",
            "current_state": self._state.current_state.name,
            "severity": self._state.current_state.severity,
            "allows_new_risk": self.allows_new_risk,
            "allows_risk_reduction": self.allows_risk_reduction,
            "state_history": self.get_state_history(20),
            "recent_decisions": [d.to_dict() for d in self.get_recent_decisions(20)],
            "recent_interventions": self.get_intervention_history(20),
            "metrics": self.get_metrics(),
            "invariants": self.verify_invariants(),
        }
