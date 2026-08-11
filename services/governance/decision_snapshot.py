"""
Decision Snapshot — complete frozen state at decision time.

Captures ALL relevant state so decisions can be replayed and audited:
  Market, Risk, Strategy, Policy, Authority, Approval, Allocation.

Each section has its own hash for component-level integrity checking.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .audit_hash import AuditHash


@dataclass
class DecisionSnapshot:
    """Frozen state of the entire governance system at decision time.

    This is the most critical data structure for audit and replay.
    Without this, you cannot reliably answer:
      "What was the system state when this decision was made?"
    """

    snapshot_id: str
    decision_id: str

    # ── Market Snapshot ──
    market_snapshot: Dict[str, Any] = field(default_factory=dict)
    market_hash: str = ""

    # ── Strategy Snapshot ──
    strategy_id: str = ""
    strategy_version: str = ""
    strategy_state: Dict[str, Any] = field(default_factory=dict)

    # ── Signal Snapshot ──
    signal_id: str = ""
    signal_type: str = ""
    signal_value: float = 0.0
    signal_confidence: float = 0.0

    # ── Risk Snapshot ──
    risk_snapshot: Dict[str, Any] = field(default_factory=dict)
    risk_hash: str = ""

    # ── Allocation Snapshot ──
    allocation_snapshot: Dict[str, Any] = field(default_factory=dict)

    # ── Policy Snapshot ──
    policy_id: str = ""
    policy_version: str = ""
    policy_hash: str = ""
    policy_snapshot: Dict[str, Any] = field(default_factory=dict)

    # ── Authority Snapshot ──
    authority_id: str = ""
    authority_snapshot: Dict[str, Any] = field(default_factory=dict)
    authority_hash: str = ""

    # ── Approval Snapshot ──
    approval_id: str = ""
    approval_snapshot: Dict[str, Any] = field(default_factory=dict)
    approval_hash: str = ""

    # ── Decision Data ──
    decision_type: str = ""
    instrument: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0

    # ── Integrity ──
    snapshot_hash: str = ""
    correlation_id: str = ""

    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute the full snapshot hash."""
        data = {
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "market_snapshot": self.market_snapshot,
            "risk_snapshot": self.risk_snapshot,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "authority_id": self.authority_id,
            "approval_id": self.approval_id,
            "decision_type": self.decision_type,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "amount": self.amount,
            "timestamp": self.timestamp,
        }
        self.snapshot_hash = AuditHash.compute_snapshot_hash(data)
        return self.snapshot_hash

    def compute_component_hashes(self) -> None:
        """Compute individual component hashes."""
        if self.market_snapshot:
            self.market_hash = AuditHash.compute_snapshot_hash(self.market_snapshot)
        if self.risk_snapshot:
            self.risk_hash = AuditHash.compute_snapshot_hash(self.risk_snapshot)
        if self.policy_snapshot:
            self.policy_hash = AuditHash.compute_snapshot_hash(self.policy_snapshot)
        if self.authority_snapshot:
            self.authority_hash = AuditHash.compute_snapshot_hash(self.authority_snapshot)
        if self.approval_snapshot:
            self.approval_hash = AuditHash.compute_snapshot_hash(self.approval_snapshot)

    def verify(self) -> Dict[str, Any]:
        """Verify all component hashes."""
        expected_full = AuditHash.compute_snapshot_hash({
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "market_snapshot": self.market_snapshot,
            "risk_snapshot": self.risk_snapshot,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "authority_id": self.authority_id,
            "approval_id": self.approval_id,
            "decision_type": self.decision_type,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "amount": self.amount,
            "timestamp": self.timestamp,
        })

        checks = {
            "full_snapshot": {
                "valid": self.snapshot_hash == expected_full,
                "expected": expected_full,
                "actual": self.snapshot_hash,
            },
        }

        if self.market_hash:
            expected_m = AuditHash.compute_snapshot_hash(self.market_snapshot)
            checks["market"] = {
                "valid": self.market_hash == expected_m,
            }
        if self.risk_hash:
            expected_r = AuditHash.compute_snapshot_hash(self.risk_snapshot)
            checks["risk"] = {
                "valid": self.risk_hash == expected_r,
            }
        if self.policy_hash:
            expected_p = AuditHash.compute_snapshot_hash(self.policy_snapshot)
            checks["policy"] = {
                "valid": self.policy_hash == expected_p,
            }
        if self.authority_hash:
            expected_a = AuditHash.compute_snapshot_hash(self.authority_snapshot)
            checks["authority"] = {
                "valid": self.authority_hash == expected_a,
            }
        if self.approval_hash:
            expected_ap = AuditHash.compute_snapshot_hash(self.approval_snapshot)
            checks["approval"] = {
                "valid": self.approval_hash == expected_ap,
            }

        all_valid = all(c.get("valid", True) for c in checks.values())
        return {"valid": all_valid, "checks": checks}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "market_snapshot": self.market_snapshot,
            "market_hash": self.market_hash,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "strategy_state": self.strategy_state,
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "signal_value": self.signal_value,
            "signal_confidence": self.signal_confidence,
            "risk_snapshot": self.risk_snapshot,
            "risk_hash": self.risk_hash,
            "allocation_snapshot": self.allocation_snapshot,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "policy_snapshot": self.policy_snapshot,
            "authority_id": self.authority_id,
            "authority_snapshot": self.authority_snapshot,
            "authority_hash": self.authority_hash,
            "approval_id": self.approval_id,
            "approval_snapshot": self.approval_snapshot,
            "approval_hash": self.approval_hash,
            "decision_type": self.decision_type,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "snapshot_hash": self.snapshot_hash,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionSnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            decision_id=data.get("decision_id", ""),
            market_snapshot=data.get("market_snapshot", {}),
            market_hash=data.get("market_hash", ""),
            strategy_id=data.get("strategy_id", ""),
            strategy_version=data.get("strategy_version", ""),
            strategy_state=data.get("strategy_state", {}),
            signal_id=data.get("signal_id", ""),
            signal_type=data.get("signal_type", ""),
            signal_value=data.get("signal_value", 0.0),
            signal_confidence=data.get("signal_confidence", 0.0),
            risk_snapshot=data.get("risk_snapshot", {}),
            risk_hash=data.get("risk_hash", ""),
            allocation_snapshot=data.get("allocation_snapshot", {}),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            policy_hash=data.get("policy_hash", ""),
            policy_snapshot=data.get("policy_snapshot", {}),
            authority_id=data.get("authority_id", ""),
            authority_snapshot=data.get("authority_snapshot", {}),
            authority_hash=data.get("authority_hash", ""),
            approval_id=data.get("approval_id", ""),
            approval_snapshot=data.get("approval_snapshot", {}),
            approval_hash=data.get("approval_hash", ""),
            decision_type=data.get("decision_type", ""),
            instrument=data.get("instrument", ""),
            side=data.get("side", ""),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            amount=data.get("amount", 0.0),
            snapshot_hash=data.get("snapshot_hash", ""),
            correlation_id=data.get("correlation_id", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )
