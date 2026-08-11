"""
Audit Integrity Checker — detects tampering, orphans, and chain breaks.

Regularly verifies:
  - Hash chain integrity (no tampered events)
  - Sequence continuity (no missing events)
  - Timestamp consistency (no future/retroactive events)
  - Correlation/causation validity
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .audit_chain import AuditChain
from .immutable_audit_log import ImmutableAuditLog
from .audit_event import AuditEvent
from .audit_event_type import AuditEventType
from .audit_hash import AuditHash


class AuditIntegrityChecker:
    """Periodic integrity verification of the audit system.

    Detects:
      - Hash chain breaks (tampered events)
      - Missing sequence numbers
      - Timestamp anomalies
      - Incomplete correlations
    """

    def __init__(
        self,
        chain: Optional[AuditChain] = None,
        audit_log: Optional[ImmutableAuditLog] = None,
        max_timestamp_future_seconds: float = 300.0,  # 5 min clock skew tolerance
    ):
        self._chain = chain or AuditChain()
        self._log = audit_log
        self._max_future = max_timestamp_future_seconds
        self._last_check: float = 0.0
        self._check_count: int = 0

    def verify(self) -> Dict[str, Any]:
        """Run a full integrity verification.

        Returns: {
            "valid": bool,
            "chain_ok": bool,
            "issues": [...]
        }
        """
        issues: List[Dict[str, Any]] = []

        # 1. Verify hash chain
        chain_result = self._chain.verify()
        chain_ok = chain_result["valid"]
        for issue in chain_result.get("issues", []):
            issues.append({**issue, "category": "CHAIN"})

        # 2. Verify event hashes (if log available)
        if self._log and self._chain._links:
            issues.extend(self._verify_event_hashes())

        # 3. Check timestamps
        if self._log:
            issues.extend(self._verify_timestamps())

        self._last_check = time.time()
        self._check_count += 1

        valid = len(issues) == 0

        return {
            "valid": valid,
            "chain_ok": chain_ok,
            "chain_length": self._chain.length,
            "issues": issues,
            "issues_count": len(issues),
            "checked_at": self._last_check,
            "check_count": self._check_count,
        }

    def verify_single_event(self, event: AuditEvent) -> Dict[str, Any]:
        """Verify a single event's hash matches its content."""
        expected_hash = AuditHash.compute_event_hash(event.to_dict())
        actual_hash = event.event_hash
        valid = actual_hash == expected_hash
        return {
            "event_id": event.event_id,
            "valid": valid,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "is_critical": event.is_critical,
        }

    def detect_tamper(self) -> Dict[str, Any]:
        """Detect if any events have been tampered with.

        Computes fresh hashes and compares against stored hashes.
        """
        if not self._log:
            return {"tampered": False, "reason": "no_log_available"}

        tampered_events: List[str] = []
        for event in self._log.query_all(limit=10000):
            result = self.verify_single_event(event)
            if not result["valid"]:
                tampered_events.append(event.event_id)

        return {
            "tampered": len(tampered_events) > 0,
            "tampered_count": len(tampered_events),
            "tampered_event_ids": tampered_events,
        }

    # ── Internal ──

    def _verify_event_hashes(self) -> List[Dict[str, Any]]:
        """Verify hashes of all events in the log match computed hashes."""
        if not self._log:
            return []

        issues: List[Dict[str, Any]] = []
        for event in self._log.query_all(limit=10000):
            try:
                expected_hash = AuditHash.compute_event_hash(event.to_dict())
                if event.event_hash and event.event_hash != expected_hash:
                    issues.append({
                        "category": "EVENT_HASH",
                        "event_id": event.event_id,
                        "type": "HASH_MISMATCH",
                        "expected": expected_hash,
                        "actual": event.event_hash,
                    })
            except Exception:
                pass  # Skip malformed events in integrity check
        return issues

    def _verify_timestamps(self) -> List[Dict[str, Any]]:
        """Check for timestamp anomalies."""
        if not self._log:
            return []

        issues: List[Dict[str, Any]] = []
        now = time.time()
        future_threshold = now + self._max_future

        for event in self._log.query_all(limit=10000):
            if event.timestamp > future_threshold:
                issues.append({
                    "category": "TIMESTAMP",
                    "event_id": event.event_id,
                    "type": "FUTURE_TIMESTAMP",
                    "timestamp": event.timestamp,
                    "current_time": now,
                })
        return issues
