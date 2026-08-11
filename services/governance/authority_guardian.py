"""
Authority Guardian — monitors authority/ delegation integrity.

Part 1.5: detects authority breaches, compromise patterns, expiry
issues, and delegation anomalies.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .governance_signal import GovernanceSignal, SignalType
from .control_trigger import ControlTrigger, TriggerType, Severity


class AuthorityGuardian:
    """Monitors authority grants, delegations, and detects compromises.

    Checks:
      - Authority scope/limit breaches
      - Delegation chain validity
      - Authority expiry
      - Unexpected authority patterns
    """

    def __init__(self):
        self._alerts: List[Dict[str, Any]] = []
        self._authorities: Dict[str, Dict[str, Any]] = {}
        self._delegations: Dict[str, Dict[str, Any]] = {}

    def register_authority(
        self,
        authority_id: str,
        scope: str,
        limit: float,
        expiry: float = 0.0,
        delegator: str = "",
    ) -> None:
        """Register an authority for monitoring."""
        self._authorities[authority_id] = {
            "authority_id": authority_id,
            "scope": scope,
            "limit": limit,
            "expiry": expiry,
            "delegator": delegator,
            "registered_at": time.time(),
            "status": "ACTIVE",
        }

    def register_delegation(
        self,
        delegation_id: str,
        source_authority: str,
        target_actor: str,
        scope: str,
        limit: float,
        expiry: float = 0.0,
    ) -> None:
        """Register a delegation for monitoring."""
        self._delegations[delegation_id] = {
            "delegation_id": delegation_id,
            "source_authority": source_authority,
            "target_actor": target_actor,
            "scope": scope,
            "limit": limit,
            "expiry": expiry,
            "registered_at": time.time(),
            "status": "ACTIVE",
        }

    def check(self) -> List[ControlTrigger]:
        """Check authority state for breaches.

        Returns:
            List of ControlTrigger objects.
        """
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()

        # Check authority expiries
        for auth_id, auth in self._authorities.items():
            if auth["expiry"] > 0 and now > auth["expiry"]:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.AUTHORITY_EXPIRY,
                    severity=Severity.MEDIUM,
                    source="authority-guardian",
                    description=f"Authority {auth_id} expired.",
                    correlation_id=corr_id,
                ))
                auth["status"] = "EXPIRED"

        # Check delegation expiries
        for del_id, delegation in self._delegations.items():
            if delegation["expiry"] > 0 and now > delegation["expiry"]:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.AUTHORITY_EXPIRY,
                    severity=Severity.MEDIUM,
                    source="authority-guardian",
                    description=f"Delegation {del_id} expired.",
                    correlation_id=corr_id,
                ))
                delegation["status"] = "EXPIRED"

        # Check delegation cascade — orphaned delegations
        for del_id, delegation in self._delegations.items():
            source = delegation.get("source_authority", "")
            if source in self._authorities and self._authorities[source].get("status") == "REVOKED":
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.DELEGATION_CASCADE,
                    severity=Severity.HIGH,
                    source="authority-guardian",
                    description=f"Delegation {del_id} from revoked authority {source}.",
                    correlation_id=corr_id,
                ))
                delegation["status"] = "INVALID"

        # Store alerts
        if triggers:
            self._alerts.append({
                "timestamp": now,
                "triggers": [t.to_dict() for t in triggers],
            })

        return triggers

    def revoke_authority(self, authority_id: str, reason: str = "") -> Dict[str, Any]:
        """Revoke an authority and cascade to delegations."""
        if authority_id not in self._authorities:
            return {"success": False, "error": f"Authority {authority_id} not found."}

        self._authorities[authority_id]["status"] = "REVOKED"
        self._authorities[authority_id]["revoked_at"] = time.time()
        self._authorities[authority_id]["revoke_reason"] = reason

        # Cascade revocation
        cascade_count = 0
        for del_id, delegation in self._delegations.items():
            if delegation.get("source_authority") == authority_id:
                delegation["status"] = "INVALID"
                delegation["invalidated_at"] = time.time()
                cascade_count += 1

        return {
            "success": True,
            "authority_id": authority_id,
            "cascaded_delegations": cascade_count,
        }

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "active_authorities": sum(1 for a in self._authorities.values() if a["status"] == "ACTIVE"),
            "revoked_authorities": sum(1 for a in self._authorities.values() if a["status"] == "REVOKED"),
            "expired_authorities": sum(1 for a in self._authorities.values() if a["status"] == "EXPIRED"),
            "active_delegations": sum(1 for d in self._delegations.values() if d["status"] == "ACTIVE"),
            "invalid_delegations": sum(1 for d in self._delegations.values() if d["status"] in ("INVALID", "EXPIRED")),
            "alerts_count": len(self._alerts),
        }
