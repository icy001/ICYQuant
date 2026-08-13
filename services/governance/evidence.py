"""Evidence — immutable governance decision evidence (Commit 28 Part 1.5).

Decision 本身还不够。需要保存 Decision 当时使用的关键输入（Policy 版本、
Authority、Approval、Context Hash），这样即使 Policy 后续更新，仍然能够
重建"DEC-001 当时是依据 Policy v3 做出的"。

    Decision
        ├── policy
        ├── authority
        ├── approval
        └── context
               │
               ▼
            Evidence
               │
               ▼
            Hash (EvidenceEnvelope)

Context 通过 Canonical Serialization -> SHA-256 得到 context_hash，避免
把整个 Context 无限复制进 Ledger；Evidence 本身也要 Hash，从而可以检测
Evidence 是否被修改（Part 1.5 §14/§17/§18/§24/§25）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone


def canonicalize_context(context) -> str:
    """Stable canonical serialization of a context / payload (Part 1.5 §18).

    ``{"a":1,"b":2}`` and ``{"b":2,"a":1}`` hash to the same value because
    keys are sorted and separators are stable.
    """
    return json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
    )


def context_hash(context) -> str:
    """SHA-256 of a canonicalized context (Part 1.5 §17)."""
    return hashlib.sha256(canonicalize_context(context).encode()).hexdigest()


@dataclass(frozen=True)
class GovernanceEvidence:
    """The immutable inputs a decision was based on (Part 1.5 §14).

    ``authority_snapshot`` captures the authorities that were effective at
    decision time; ``policy_version`` captures the exact policy version used;
    ``approval_id`` / ``approval_state`` / ``quorum_met`` capture the
    approval chain; ``context_hash`` proves which system/risk/market state
    the decision was made in.
    """

    decision_id: str
    policy_id: str | None
    policy_version: str | None
    principal_id: str
    authority_snapshot: tuple[str, ...]
    approval_id: str | None
    approval_state: str | None
    quorum_met: bool | None
    context_hash: str
    created_at: datetime


def evidence_hash(evidence: GovernanceEvidence) -> str:
    """SHA-256 over the canonical form of an evidence record (Part 1.5 §24)."""
    payload = {
        "decision_id": evidence.decision_id,
        "policy_id": evidence.policy_id,
        "policy_version": evidence.policy_version,
        "principal_id": evidence.principal_id,
        "authority_snapshot": list(evidence.authority_snapshot),
        "approval_id": evidence.approval_id,
        "approval_state": evidence.approval_state,
        "quorum_met": evidence.quorum_met,
        "context_hash": evidence.context_hash,
        "created_at": evidence.created_at.isoformat(),
    }
    encoded = canonicalize_context(payload).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope:
    """Evidence bound to its integrity hash (Part 1.5 §24)."""

    evidence: GovernanceEvidence
    evidence_hash: str


def build_evidence(
    decision,
    policy_version: str | None = None,
    authority_snapshot: tuple[str, ...] = (),
    approval_state: str | None = None,
    quorum_met: bool | None = None,
    context_hash: str | None = None,
    created_at: datetime | None = None,
) -> EvidenceEnvelope:
    """Build an evidence envelope for a ledger decision (Part 1.5 §15)."""
    evidence = GovernanceEvidence(
        decision_id=decision.decision_id or "",
        policy_id=decision.policy_id,
        policy_version=policy_version,
        principal_id=decision.principal_id or "",
        authority_snapshot=tuple(authority_snapshot),
        approval_id=decision.approval_id,
        approval_state=approval_state,
        quorum_met=quorum_met,
        context_hash=context_hash or (decision.context_hash or ""),
        created_at=created_at
        or decision.decided_at
        or datetime.now(timezone.utc),
    )
    return EvidenceEnvelope(
        evidence=evidence,
        evidence_hash=evidence_hash(evidence),
    )


def verify_envelope(envelope: EvidenceEnvelope) -> bool:
    """True when the envelope hash still matches the evidence content."""
    return envelope.evidence_hash == evidence_hash(envelope.evidence)
