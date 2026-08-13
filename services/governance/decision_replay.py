"""Decision Replay — chain validation and historical decision replay
(Commit 28 Part 1.5).

Chain Validation (Part 1.5 §12/§13):
    D001 -> hash -> D002 -> hash -> D003
    修改任何一条 entry 都会导致其后 entry 的 previous_hash 不匹配，
    从而 CHAIN INVALID。

Decision Replay (Part 1.5 §19-§23):
    replay() 的目标不是再执行一次操作，而是重新计算当时为什么得到这个
    Decision：Input -> Policy -> Authority -> Approval -> Decision。
    Replay 永远不会触发 Control Execution（不会 pause/resume/kill trading）。

    历史 Replay 默认使用当时的 Policy 版本（evidence.policy_version），
    而不是当前版本，否则历史审计没有意义。

    Mismatch 时必须给出具体原因，而不是简单的 "Replay failed"：
        POLICY_VERSION_MISMATCH / AUTHORITY_STATE_CHANGED / APPROVAL_EXPIRED
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .audit import (
    GovernanceAuditEventType,
    GovernanceAuditStore,
    decision_to_audit_event,
)
from .decision import DecisionEffect
from .decision_ledger import DecisionEntry, DecisionLedger, calculate_hash
from .evidence import GovernanceEvidence


class DecisionChainValidator:
    """Validates the integrity of a decision hash chain (Part 1.5 §12)."""

    def validate(self, entries) -> bool:
        """True when every entry is well-formed and the chain is unbroken."""
        previous_hash = None
        for entry in entries:
            if entry.previous_hash != previous_hash:
                return False
            expected = calculate_hash(
                sequence=entry.sequence,
                decision_id=entry.decision_id,
                request_id=entry.request_id,
                effect=entry.effect,
                reason_code=entry.reason_code,
                timestamp=entry.timestamp,
                previous_hash=entry.previous_hash,
            )
            if entry.entry_hash != expected:
                return False
            previous_hash = entry.entry_hash
        return True


@dataclass(frozen=True)
class ReplayResult:
    """The outcome of re-evaluating a historical decision (Part 1.5 §21)."""

    original_decision_id: str
    original_effect: DecisionEffect
    replayed_effect: DecisionEffect
    matched: bool
    mismatches: tuple[str, ...]


class DecisionReplayer:
    """Re-computes why a historical decision was made (Part 1.5 §19).

    Uses the inputs captured in the evidence (policy version, authority,
    approval, quorum) plus the supplied historical policy / authority, and
    compares against the original decision effect.

    The original decision is located through ``original_decision`` or, when
    bound to a :class:`DecisionLedger`, by ``decision_id`` lookup.
    """

    def __init__(
        self,
        ledger: DecisionLedger | None = None,
        auditor: GovernanceAuditStore | None = None,
    ) -> None:
        self._ledger = ledger
        self._auditor = auditor

    @property
    def ledger(self) -> DecisionLedger | None:
        return self._ledger

    def replay(
        self,
        request,
        evidence: GovernanceEvidence,
        policy,
        authority,
        original_decision=None,
    ) -> ReplayResult:
        """Recompute the decision for a historical request + evidence."""
        original = original_decision
        if original is None and self._ledger is not None:
            original = self._ledger.get_by_decision(evidence.decision_id)

        original_id = evidence.decision_id
        original_effect = DecisionEffect.DENY
        if original is not None:
            original_id = getattr(original, "decision_id", None) or original_id
            effect = getattr(original, "effect", None)
            if effect is not None:
                original_effect = effect

        mismatches: list[str] = []
        replayed = self._reevaluate(request, evidence, policy, authority, mismatches)
        matched = replayed == original_effect and not mismatches

        result = ReplayResult(
            original_decision_id=original_id,
            original_effect=original_effect,
            replayed_effect=replayed,
            matched=matched,
            mismatches=tuple(mismatches),
        )
        self._record_audit(evidence, result)
        return result

    # -- internals ---------------------------------------------------------
    def _reevaluate(
        self,
        request,
        evidence: GovernanceEvidence,
        policy,
        authority,
        mismatches: list[str],
    ) -> DecisionEffect:
        # 1) Policy identity + version (Part 1.5 §23)
        policy_id = getattr(policy, "policy_id", None)
        if policy is None or policy_id != evidence.policy_id:
            mismatches.append("POLICY_VERSION_MISMATCH")
            return DecisionEffect.DENY
        if evidence.policy_version is not None and getattr(
            policy, "version", None
        ) != evidence.policy_version:
            mismatches.append("POLICY_VERSION_MISMATCH")
            return DecisionEffect.DENY

        # 2) Authority re-check (Part 1.5 §22)
        resource = getattr(request, "resource", None)
        action = getattr(request, "action", None)
        if authority is None or (
            resource is not None
            and not authority.allows(resource, action)
        ):
            mismatches.append("AUTHORITY_STATE_CHANGED")
            return DecisionEffect.DENY

        # 3) Approval re-check
        if evidence.approval_id is not None:
            if evidence.approval_state != "APPROVED":
                mismatches.append("APPROVAL_EXPIRED")
                return DecisionEffect.DENY

        # 4) Quorum re-check
        if evidence.quorum_met is False:
            mismatches.append("QUORUM_NOT_MET")
            return DecisionEffect.DENY

        # 5) Policy effect (approval already satisfied -> ALLOW)
        return self._policy_effect(policy, evidence)

    def _policy_effect(self, policy, evidence: GovernanceEvidence) -> DecisionEffect:
        effect = getattr(policy, "effect", "ALLOW")
        if effect == "DENY":
            return DecisionEffect.DENY
        if effect == "REQUIRE_APPROVAL":
            if (
                evidence.approval_id is not None
                and evidence.approval_state == "APPROVED"
            ):
                return DecisionEffect.ALLOW
            return DecisionEffect.REQUIRE_APPROVAL
        return DecisionEffect.ALLOW

    def _record_audit(self, evidence: GovernanceEvidence, result: ReplayResult) -> None:
        if self._auditor is None:
            return
        event_type = (
            GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAYED
            if result.matched
            else GovernanceAuditEventType.GOVERNANCE_DECISION_REPLAY_MISMATCH
        )
        self._auditor.record(
            decision_to_audit_event(
                evidence,
                event_type,
            )
        )
