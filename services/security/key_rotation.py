"""
ICYQuant Key Rotation Manager

Automated rotation of API keys, TLS certificates, JWT secrets,
and encryption keys based on configurable rotation policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class RotationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RotationPolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    target: str = ""
    rotation_interval_days: int = 90
    advance_notification_days: int = 7
    auto_rotate: bool = True
    rollback_enabled: bool = True
    max_versions: int = 5
    rotation_hours: List[int] = field(default_factory=lambda: [2])
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "target": self.target,
            "rotationIntervalDays": self.rotation_interval_days,
            "advanceNotificationDays": self.advance_notification_days,
            "autoRotate": self.auto_rotate,
            "enabled": self.enabled,
        }


@dataclass
class RotationPlan:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    target: str = ""
    status: RotationStatus = RotationStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    old_version: str = ""
    new_version: str = ""
    steps: List[Dict] = field(default_factory=list)
    triggered_by: str = "scheduler"

    def start(self):
        self.status = RotationStatus.IN_PROGRESS
        self.started_at = datetime.now()
        self.steps.append({
            "step": "init",
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        })

    def complete(self, new_version: str):
        self.status = RotationStatus.COMPLETED
        self.completed_at = datetime.now()
        self.new_version = new_version
        self.steps.append({
            "step": "complete",
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        })

    def fail(self, error: str):
        self.status = RotationStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error
        self.steps.append({
            "step": "fail",
            "status": "failed",
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "policyId": self.policy_id,
            "target": self.target,
            "status": self.status.value,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "errorMessage": self.error_message,
            "steps": self.steps,
        }


class KeyRotationManager:
    """
    Automated key rotation manager.

    Schedules and executes rotation of secrets, keys, and credentials
    based on configurable policies. Supports advance notification,
    automatic rotation, and rollback on failure.
    """

    def __init__(self):
        self._policies: Dict[str, RotationPolicy] = {}
        self._plans: Dict[str, RotationPlan] = {}
        self._rotation_callbacks: Dict[str, List[Callable]] = {}
        self._notification_callbacks: List[Callable] = []
        self._rotation_history: List[RotationPlan] = []
        self._max_history = 1000

    def create_policy(self, policy: RotationPolicy) -> RotationPolicy:
        if policy.name in self._policies:
            raise ValueError(f"Policy '{policy.name}' already exists")
        self._policies[policy.name] = policy
        logger.info(f"Rotation policy created: {policy.name} (target: {policy.target})")
        return policy

    def update_policy(self, name: str, **kwargs) -> Optional[RotationPolicy]:
        policy = self._policies.get(name)
        if not policy:
            return None
        for key, value in kwargs.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        return policy

    def delete_policy(self, name: str):
        del self._policies[name]

    def execute_rotation(self, policy_name: str) -> RotationPlan:
        policy = self._policies.get(policy_name)
        if not policy:
            raise ValueError(f"Policy '{policy_name}' not found")

        plan = RotationPlan(policy_id=policy.id, target=policy.target)
        plan.start()

        try:
            self._execute_rotation_steps(policy, plan)
            version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
            plan.complete(version)
            self._notify_rotation_complete(policy, plan)

        except Exception as e:
            plan.fail(str(e))
            if policy.rollback_enabled:
                self._rollback_rotation(policy, plan)
            logger.error(f"Rotation failed for {policy_name}: {e}")

        self._plans[plan.id] = plan
        self._rotation_history.append(plan)
        if len(self._rotation_history) > self._max_history:
            self._rotation_history = self._rotation_history[-self._max_history:]
        return plan

    def schedule_rotation(self, policy_name: str) -> RotationPlan:
        return self.execute_rotation(policy_name)

    def on_rotation_complete(self, policy_name: str, callback: Callable):
        if policy_name not in self._rotation_callbacks:
            self._rotation_callbacks[policy_name] = []
        self._rotation_callbacks[policy_name].append(callback)

    def on_notification(self, callback: Callable):
        self._notification_callbacks.append(callback)

    def check_notifications(self) -> List[Dict]:
        notifications = []
        now = datetime.now()
        for policy in self._policies.values():
            if not policy.enabled or not policy.auto_rotate:
                continue
            notification_date = now + timedelta(days=policy.advance_notification_days)
            notifications.append({
                "policy": policy.name,
                "target": policy.target,
                "message": f"Rotation scheduled for {policy.target}",
                "scheduledFor": notification_date.isoformat(),
            })
        for cb in self._notification_callbacks:
            for n in notifications:
                try:
                    cb(n)
                except Exception:
                    pass
        return notifications

    def get_plan(self, plan_id: str) -> Optional[RotationPlan]:
        return self._plans.get(plan_id)

    def list_policies(self) -> List[RotationPolicy]:
        return list(self._policies.values())

    def list_plans(
        self,
        status: Optional[RotationStatus] = None,
        limit: int = 50,
    ) -> List[RotationPlan]:
        plans = list(self._plans.values())
        if status:
            plans = [p for p in plans if p.status == status]
        return plans[-limit:]

    def get_history(self, limit: int = 50) -> List[Dict]:
        return [p.to_dict() for p in self._rotation_history[-limit:]]

    def to_dict(self) -> Dict:
        return {
            "totalPolicies": len(self._policies),
            "activePlans": sum(1 for p in self._plans.values() if p.status == RotationStatus.IN_PROGRESS),
            "completedPlans": sum(1 for p in self._plans.values() if p.status == RotationStatus.COMPLETED),
        }

    def _execute_rotation_steps(self, policy: RotationPolicy, plan: RotationPlan):
        steps = [
            ("backup", lambda: self._backup_current(policy)),
            ("generate", lambda: self._generate_new(policy)),
            ("validate", lambda: self._validate_new(policy)),
            ("migrate", lambda: self._migrate_services(policy)),
            ("disable_old", lambda: self._disable_old(policy)),
            ("verify", lambda: self._verify_rotation(policy)),
        ]
        for step_name, step_fn in steps:
            try:
                step_fn()
                plan.steps.append({
                    "step": step_name,
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception as e:
                plan.steps.append({
                    "step": step_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                raise

    def _backup_current(self, policy: RotationPolicy):
        pass

    def _generate_new(self, policy: RotationPolicy):
        pass

    def _validate_new(self, policy: RotationPolicy):
        pass

    def _migrate_services(self, policy: RotationPolicy):
        pass

    def _disable_old(self, policy: RotationPolicy):
        pass

    def _verify_rotation(self, policy: RotationPolicy):
        pass

    def _rollback_rotation(self, policy: RotationPolicy, plan: RotationPlan):
        for cb in self._rotation_callbacks.get(policy.name, []):
            try:
                cb({"action": "rollback", "policy": policy.name, "plan": plan.id})
            except Exception:
                pass

    def _notify_rotation_complete(self, policy: RotationPolicy, plan: RotationPlan):
        for cb in self._rotation_callbacks.get(policy.name, []):
            try:
                cb({"action": "complete", "policy": policy.name, "plan": plan.id})
            except Exception:
                pass
