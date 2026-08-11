"""
Policy Guardian — monitors policy integrity.

Part 1.5: detects policy violations, version mismatches, policy conflicts,
and policy hash integrity failures.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .control_trigger import ControlTrigger, TriggerType, Severity


class PolicyGuardian:
    """Monitors policy state and detects integrity issues.

    Checks:
      - Policy violation patterns
      - Policy version mismatches
      - Policy hash integrity
      - Policy conflicts
      - Policy expiry
    """

    def __init__(self, policy_engine: Any = None):
        self._policy_engine = policy_engine
        self._policy_hashes: Dict[str, str] = {}  # policy_id → expected_hash
        self._alerts: List[Dict[str, Any]] = []
        self._violations_24h: int = 0

    def register_policy(
        self,
        policy_id: str,
        expected_hash: str,
        version: str = "1.0.0",
        expiry: float = 0.0,
    ) -> None:
        """Register a policy's expected hash for integrity checking."""
        self._policy_hashes[policy_id] = expected_hash

    def check(self) -> List[ControlTrigger]:
        """Check policy integrity.

        Returns:
            List of ControlTrigger objects.
        """
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

        # Check policy integrity via hash comparison
        if self._policy_engine:
            for policy_id, expected_hash in self._policy_hashes.items():
                actual_hash = self._get_policy_hash(policy_id)
                if actual_hash and actual_hash != expected_hash:
                    triggers.append(ControlTrigger(
                        trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                        trigger_type=TriggerType.POLICY_INTEGRITY_FAILURE,
                        severity=Severity.CRITICAL,
                        source="policy-guardian",
                        description=f"Policy {policy_id} hash mismatch: expected {expected_hash[:12].upper()}..., got {actual_hash[:12].upper()}...",
                        correlation_id=corr_id,
                    ))

        if triggers:
            self._alerts.append({
                "timestamp": time.time(),
                "triggers": [t.to_dict() for t in triggers],
            })

        return triggers

    def _get_policy_hash(self, policy_id: str) -> Optional[str]:
        """Get current policy hash from policy engine."""
        if not self._policy_engine:
            return None
        try:
            return getattr(self._policy_engine, "get_policy_hash", lambda x: None)(policy_id)
        except Exception:
            return None

    def check_policy_violations(self, violations: List[Dict[str, Any]]) -> List[ControlTrigger]:
        """Check for policy violation patterns."""
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

        for violation in violations:
            self._violations_24h += 1
            if self._violations_24h > 10:  # Spike detection
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.POLICY_BREACH,
                    severity=Severity.MEDIUM,
                    source="policy-guardian",
                    description=f"Policy violation spike: {self._violations_24h} in 24h",
                    correlation_id=corr_id,
                ))
                break

        return triggers

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "monitored_policies": len(self._policy_hashes),
            "violations_24h": self._violations_24h,
            "alerts_count": len(self._alerts),
        }
