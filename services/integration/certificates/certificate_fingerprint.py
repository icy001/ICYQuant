"""CertificateFingerprint — unique identifier for certificate content.

The certificate fingerprint is a SHA-256 hash over the certificate's
core identifiers and evidence. It serves as:

- integrity verification key (tamper detection)
- replay protection key (duplicate detection)
- audit index key

Unlike CertificateSignature (which includes all fields), the fingerprint
focuses on core identity: who, what, when, under what policy.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CertificateFingerprint:
    """Content-based fingerprint for a PreTradeControlCertificate."""

    fingerprint_hash: str = ""
    computed_at: float = field(default_factory=lambda: time.time())

    # ── Input components tracked ──────────────────────────────
    components: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def compute(
        cls,
        certificate_id: str,
        flow_id: str,
        order_intent_id: str,
        decision_id: str,
        signal_id: str,
        strategy_id: str,
        account_id: str,
        symbol: str,
        side: str,
        max_quantity: Optional[float],
        max_notional: Optional[float],
        venue: str,
        policy_versions: Dict[str, str],
        evidence_hash: str,
    ) -> "CertificateFingerprint":
        """Compute fingerprint from core certificate identity fields."""
        components = {
            "certificate_id": certificate_id,
            "flow_id": flow_id,
            "order_intent_id": order_intent_id,
            "decision_id": decision_id,
            "signal_id": signal_id,
            "strategy_id": strategy_id,
            "account_id": account_id,
            "symbol": symbol.upper() if symbol else "",
            "side": side.upper() if side else "",
            "max_quantity": str(max_quantity) if max_quantity is not None else "",
            "max_notional": str(max_notional) if max_notional is not None else "",
            "venue": venue.upper() if venue else "",
            "policy_versions": json.dumps(
                dict(sorted(policy_versions.items())), sort_keys=True
            ),
            "evidence_hash": evidence_hash,
        }

        raw = json.dumps(components, sort_keys=True, default=str)
        fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return cls(fingerprint_hash=fp, components=components)

    def matches(self, other: "CertificateFingerprint") -> bool:
        """Check whether two fingerprints are identical."""
        return self.fingerprint_hash == other.fingerprint_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_hash": self.fingerprint_hash,
            "computed_at": self.computed_at,
            "components": self.components,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateFingerprint(hash={self.fingerprint_hash[:16]}...)"
        )
