"""CertificateSignature — integrity signature for PreTradeControlCertificate.

The signature is a SHA-256 hash computed over the certificate's immutable
fields. Any modification to scope, constraints, claims, or evidence will
produce a different signature, making tampering detectable.

This is the core integrity mechanism that makes the certificate
"Evidence + Integrity Proof" rather than just a database record.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CertificateSignature:
    """Cryptographic-style integrity signature for certificate fields.

    Contains both the computed hash and the metadata needed to
    re-compute and verify it.
    """

    hash_value: str = ""
    algorithm: str = "sha256"
    computed_at: float = field(default_factory=lambda: time.time())

    # ── Fields included in the hash computation ───────────────
    included_fields: List[str] = field(default_factory=list)

    @classmethod
    def compute(
        cls,
        certificate_id: str,
        flow_id: str,
        order_intent_id: str,
        intent_hash: str,
        scope_info: Dict[str, Any],
        constraints_info: Dict[str, Any],
        policy_versions: Dict[str, str],
        claims_list: List[Dict[str, Any]],
        evidence_list: List[Dict[str, Any]],
    ) -> "CertificateSignature":
        """Compute the signature over all certificate integrity fields."""
        payload = {
            "certificate_id": certificate_id,
            "flow_id": flow_id,
            "order_intent_id": order_intent_id,
            "intent_hash": intent_hash,
            "scope": scope_info,
            "constraints": constraints_info,
            "policy_versions": dict(sorted(policy_versions.items())),
            "claims": claims_list,
            "evidence": evidence_list,
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        hash_val = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return cls(
            hash_value=hash_val,
            algorithm="sha256",
            included_fields=list(payload.keys()),
        )

    def verify(
        self,
        certificate_id: str,
        flow_id: str,
        order_intent_id: str,
        intent_hash: str,
        scope_info: Dict[str, Any],
        constraints_info: Dict[str, Any],
        policy_versions: Dict[str, str],
        claims_list: List[Dict[str, Any]],
        evidence_list: List[Dict[str, Any]],
    ) -> bool:
        """Re-compute and compare the signature for integrity verification."""
        recomputed = CertificateSignature.compute(
            certificate_id=certificate_id,
            flow_id=flow_id,
            order_intent_id=order_intent_id,
            intent_hash=intent_hash,
            scope_info=scope_info,
            constraints_info=constraints_info,
            policy_versions=policy_versions,
            claims_list=claims_list,
            evidence_list=evidence_list,
        )
        return self.hash_value == recomputed.hash_value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash_value": self.hash_value,
            "algorithm": self.algorithm,
            "computed_at": self.computed_at,
            "included_fields": self.included_fields,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateSignature(hash={self.hash_value[:16]}..., "
            f"algo={self.algorithm})"
        )
