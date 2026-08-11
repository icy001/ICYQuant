"""Contract Fingerprint — cryptographic identity and replay protection for contracts.

Generates deterministic fingerprints from contract content for:
  - Idempotency: same input → same fingerprint.
  - Integrity: any change → different fingerprint.
  - Replay detection: duplicate fingerprint → potential replay.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from .contracts.control_contract import ControlContract
from .contracts.contract_errors import ContractReplayError


# ── Fingerprint result ──

@dataclass
class FingerprintResult:
    """Container for a contract fingerprint and its digest."""

    fingerprint: str = ""
    algorithm: str = "sha256"
    computed_at: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"FingerprintResult({self.fingerprint[:16]}..., {self.algorithm})"


# ── Contract Fingerprint ──

@dataclass
class ContractFingerprint:
    """Computes and verifies cryptographic fingerprints for contracts.

    The fingerprint is computed from:
      - contract_id
      - contract_version
      - request (request_id + payload keys)
      - context.flow_id
      - constraint rule_ids
    """

    algorithm: str = "sha256"

    # ── Replay store ──

    _seen_fingerprints: Dict[str, float] = field(default_factory=dict)
    # Maps fingerprint → first_seen_at timestamp

    # ── Compute ──

    def compute(self, contract: ControlContract) -> FingerprintResult:
        """Generate a deterministic fingerprint for a contract."""
        canonical = self._canonical_form(contract)
        raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        digest = hashlib.new(self.algorithm, raw.encode("utf-8")).hexdigest()
        return FingerprintResult(
            fingerprint=digest,
            algorithm=self.algorithm,
        )

    def _canonical_form(self, contract: ControlContract) -> Dict[str, Any]:
        """Build a canonical dictionary for fingerprinting (deterministic ordering)."""
        return {
            "contract_id": contract.contract_id,
            "contract_version": contract.contract_version,
            "request_id": contract.request.request_id,
            "request_domain": contract.request.domain,
            "request_payload_keys": sorted(contract.request.payload.keys()),
            "flow_id": contract.context.flow_id,
            "decision_id": contract.context.decision_id,
            "strategy_id": contract.context.strategy_id,
            "constraint_rule_ids": sorted(
                c.rule_id for c in contract.constraints if c.rule_id
            ),
        }

    # ── Replay protection ──

    def check_replay(self, contract: ControlContract) -> bool:
        """Check whether this contract has been seen before.

        Returns True if it IS a replay (duplicate), False if it's new.

        Raises ContractReplayError if a replay is detected.
        """
        fp = self.compute(contract)
        if fp.fingerprint in self._seen_fingerprints:
            first_seen = self._seen_fingerprints[fp.fingerprint]
            raise ContractReplayError(
                message=f"Replay detected: contract {contract.contract_id} "
                        f"fingerprint {fp.fingerprint[:16]}... first seen at {first_seen}",
                fingerprint=fp.fingerprint,
                flow_id=contract.context.flow_id,
            )
        return False

    def record(self, contract: ControlContract) -> str:
        """Record a contract's fingerprint in the replay store.

        Returns the fingerprint string.
        """
        fp = self.compute(contract)
        self._seen_fingerprints[fp.fingerprint] = time.time()
        return fp.fingerprint

    def check_and_record(self, contract: ControlContract) -> str:
        """Check for replay, then record. Returns fingerprint.

        Raises ContractReplayError on replay.
        """
        self.check_replay(contract)
        return self.record(contract)

    # ── Integrity verification ──

    def verify_integrity(
        self, contract: ControlContract, expected_fingerprint: str
    ) -> bool:
        """Verify that a contract's computed fingerprint matches an expected value."""
        fp = self.compute(contract)
        return fp.fingerprint == expected_fingerprint

    # ── Housekeeping ──

    @property
    def seen_count(self) -> int:
        return len(self._seen_fingerprints)

    def clear(self) -> None:
        self._seen_fingerprints.clear()

    def prune(self, ttl_seconds: float = 3600.0) -> int:
        """Remove fingerprints older than ttl_seconds. Returns count removed."""
        now = time.time()
        before = len(self._seen_fingerprints)
        self._seen_fingerprints = {
            k: v for k, v in self._seen_fingerprints.items()
            if now - v < ttl_seconds
        }
        return before - len(self._seen_fingerprints)

    def get_store_snapshot(self) -> Dict[str, float]:
        return dict(self._seen_fingerprints)

    def __repr__(self) -> str:
        return f"ContractFingerprint(seen={self.seen_count}, algorithm={self.algorithm})"
