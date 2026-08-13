"""Decision Ledger — append-only governance decision ledger (Commit 28 Part 1.5).

Governance 做出的每一个决定必须能够被永久解释、重放、审计，并证明当时
为什么允许或拒绝。本模块建立独立 Ledger：

    Governance Decision
        ↓
    Append Only（无 UPDATE / DELETE）
        ↓
    SHA-256 Hash Chain（previous_hash + entry_hash）
        ↓
    幂等：同 request_id + 同指纹 -> 返回已有 Decision
    冲突：同 request_id + 不同指纹 -> REQUEST_ID_REUSE_CONFLICT

``sequence`` 是账本内的严格递增排序号；``decision_id`` 是身份标识。
两者职责不同：UUID 用于 identity，Sequence 用于 ordering。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .audit import (
    GovernanceAuditEventType,
    GovernanceAuditStore,
    decision_to_audit_event,
)
from .authority import AuthorityResolver
from .decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
    GovernanceEngine,
    ReasonCode,
)


def request_fingerprint(
    principal_id: str,
    resource: str,
    action: str,
    parameters: dict | None = None,
    context_hash: str | None = None,
) -> str:
    """Canonical SHA-256 fingerprint of a governance request (Part 1.5 §30).

    Covers principal + resource + action + parameters + context_hash so a
    resubmitted ``request_id`` with a *different* request can be detected
    as a potential replay / mutation.
    """
    payload = {
        "principal_id": principal_id,
        "resource": resource,
        "action": action,
        "parameters": parameters,
        "context_hash": context_hash,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def calculate_hash(
    sequence: int,
    decision_id: str,
    request_id: str,
    effect: str,
    reason_code: str,
    timestamp: datetime,
    previous_hash: str | None,
) -> str:
    """SHA-256 of a single ledger entry (Part 1.5 §9)."""
    payload = {
        "sequence": sequence,
        "decision_id": decision_id,
        "request_id": request_id,
        "effect": effect,
        "reason_code": reason_code,
        "timestamp": timestamp.isoformat(),
        "previous_hash": previous_hash,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _effect_value(effect) -> str:
    """Normalise a DecisionEffect (enum or string) to its string form."""
    if isinstance(effect, DecisionEffect):
        return effect.value
    return str(effect)


def _reason_code_for(effect) -> str:
    """Map a decision effect to its standardised reason code."""
    if effect == DecisionEffect.ALLOW:
        return ReasonCode.GOV_ALLOWED.value
    if effect == DecisionEffect.REQUIRE_APPROVAL:
        return ReasonCode.GOV_APPROVAL_REQUIRED.value
    return ReasonCode.GOV_DENIED.value


@dataclass(frozen=True)
class DecisionEntry:
    """One append-only ledger entry chained to its predecessor (Part 1.5 §7)."""

    sequence: int
    decision_id: str
    request_id: str
    effect: str
    reason_code: str
    timestamp: datetime
    previous_hash: str | None
    entry_hash: str


class RequestReuseConflictError(Exception):
    """Raised when a ``request_id`` is resubmitted with a different fingerprint.

    Same ``request_id`` + different request fingerprint means a potential
    replay / mutation (Part 1.5 §29), so the ledger rejects it.
    """

    reason_code = ReasonCode.REQUEST_ID_REUSE_CONFLICT.value

    def __init__(self, request_id: str) -> None:
        super().__init__(
            f"request_id {request_id} was already decided with a "
            "different request fingerprint"
        )
        self.request_id = request_id


@dataclass(frozen=True)
class GovernanceRequest:
    """A governance request entering the decision pipeline (Part 1.5 §38).

    ``request_id`` is the idempotency key. ``parameters`` and ``context_hash``
    are part of the request fingerprint: a repeated request_id with the same
    fingerprint is idempotent, with a different fingerprint it is rejected.
    """

    request_id: str
    principal_id: str
    role_ids: tuple[str, ...] = ()
    resource: str = ""
    action: str = ""
    environment: str = "production"
    incident_id: str | None = None
    severity: str | None = None
    parameters: dict | None = None
    context_hash: str | None = None


class DecisionLedger:
    """Append-only governance decision ledger with an SHA-256 hash chain.

    Core principle (Part 1.5 §5/§10): Decision -> Append Only. There is no
    UPDATE and no DELETE — the only mutation is :meth:`append`.

    - ``sequence`` strictly increases (starts at 1) and is the ordering key.
    - every entry carries ``previous_hash`` + ``entry_hash`` so tampering
      with any entry breaks every later entry's chain (Part 1.5 §8/§13).
    - a repeated ``request_id`` with a matching fingerprint returns the
      existing entry (idempotent, Part 1.5 §27/§28); with a different
      fingerprint it raises :class:`RequestReuseConflictError`.
    """

    def __init__(self, auditor: GovernanceAuditStore | None = None) -> None:
        self._entries: list[DecisionEntry] = []
        self._decisions: dict[str, GovernanceDecision] = {}
        self._entry_by_request: dict[str, DecisionEntry] = {}
        self._fingerprints: dict[str, str] = {}
        self._last_hash: str | None = None
        self._auditor = auditor

    # -- read ------------------------------------------------------------
    @property
    def entries(self) -> tuple[DecisionEntry, ...]:
        return tuple(self._entries)

    @property
    def last_hash(self) -> str | None:
        return self._last_hash

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def auditor(self) -> GovernanceAuditStore | None:
        return self._auditor

    def get_by_request(self, request_id: str) -> GovernanceDecision | None:
        return self._decisions.get(request_id)

    def get_entry_by_request(self, request_id: str) -> DecisionEntry | None:
        return self._entry_by_request.get(request_id)

    def get_by_decision(self, decision_id: str) -> GovernanceDecision | None:
        for decision in self._decisions.values():
            if decision.decision_id == decision_id:
                return decision
        return None

    def fingerprint_for(self, request_id: str) -> str | None:
        return self._fingerprints.get(request_id)

    def next_sequence(self) -> int:
        return self.size + 1

    # -- write -----------------------------------------------------------
    def append(
        self,
        decision: GovernanceDecision,
        fingerprint: str | None = None,
    ) -> DecisionEntry:
        """Append a decision to the ledger.

        Idempotent for an identical request; raises
        :class:`RequestReuseConflictError` when the same ``request_id``
        carries a different fingerprint. Returns the ledger entry.
        """
        if not decision.request_id:
            raise ValueError("decision.request_id is required by the ledger")

        fp = fingerprint or request_fingerprint(
            decision.principal_id or "",
            decision.resource or "",
            decision.action or "",
            context_hash=decision.context_hash,
        )

        existing_entry = self._entry_by_request.get(decision.request_id)
        if existing_entry is not None:
            if self._fingerprints.get(decision.request_id) == fp:
                return existing_entry  # idempotent
            raise RequestReuseConflictError(decision.request_id)

        sequence = decision.sequence if decision.sequence is not None else self.next_sequence()
        decided_at = decision.decided_at or datetime.now(timezone.utc)
        previous_hash = self._last_hash
        entry_hash = calculate_hash(
            sequence=sequence,
            decision_id=decision.decision_id or "",
            request_id=decision.request_id,
            effect=_effect_value(decision.effect),
            reason_code=decision.reason_code or decision.reason,
            timestamp=decided_at,
            previous_hash=previous_hash,
        )

        entry = DecisionEntry(
            sequence=sequence,
            decision_id=decision.decision_id or "",
            request_id=decision.request_id,
            effect=_effect_value(decision.effect),
            reason_code=decision.reason_code or decision.reason,
            timestamp=decided_at,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )

        self._entries.append(entry)
        self._entry_by_request[decision.request_id] = entry
        self._decisions[decision.request_id] = decision
        self._fingerprints[decision.request_id] = fp
        self._last_hash = entry_hash

        if self._auditor is not None:
            self._record_audit(decision)

        return entry

    def _record_audit(self, decision: GovernanceDecision) -> None:
        if self._auditor is None:
            return
        self._auditor.record(
            decision_to_audit_event(
                decision,
                GovernanceAuditEventType.GOVERNANCE_DECISION_CREATED,
            )
        )
        effect = _effect_value(decision.effect)
        if effect == DecisionEffect.ALLOW.value:
            event_type = GovernanceAuditEventType.GOVERNANCE_DECISION_ALLOWED
        elif effect == DecisionEffect.REQUIRE_APPROVAL.value:
            event_type = GovernanceAuditEventType.GOVERNANCE_APPROVAL_REQUIRED
        else:
            event_type = GovernanceAuditEventType.GOVERNANCE_DECISION_DENIED
        self._auditor.record(decision_to_audit_event(decision, event_type))


class DecisionLedgerEngine:
    """Idempotent decision pipeline backed by the append-only ledger.

    Pipeline (Part 1.5 §38):

        Request -> Request Fingerprint -> Policy Evaluation
        -> Authority Resolution -> Final Decision -> Decision Ledger

    A repeated ``request_id`` with an identical fingerprint returns the
    already-recorded decision (idempotent). A different fingerprint returns
    a DENY decision carrying ``reason_code == REQUEST_ID_REUSE_CONFLICT``.
    """

    def __init__(
        self,
        engine: GovernanceEngine | None = None,
        ledger: DecisionLedger | None = None,
        authority_resolver: AuthorityResolver | None = None,
    ) -> None:
        self._engine = engine if engine is not None else GovernanceEngine()
        self._ledger = ledger if ledger is not None else DecisionLedger()
        self._authority_resolver = authority_resolver

    @property
    def engine(self) -> GovernanceEngine:
        return self._engine

    @property
    def ledger(self) -> DecisionLedger:
        return self._ledger

    def evaluate(
        self,
        request: GovernanceRequest,
        context: GovernanceContext | None = None,
    ) -> GovernanceDecision:
        fingerprint = request_fingerprint(
            request.principal_id,
            request.resource,
            request.action,
            parameters=request.parameters,
            context_hash=request.context_hash,
        )

        existing = self._ledger.get_by_request(request.request_id)
        if existing is not None:
            if self._ledger.fingerprint_for(request.request_id) == fingerprint:
                return existing
            return self._reuse_conflict(request)

        context = context or GovernanceContext(
            principal_id=request.principal_id,
            role_ids=request.role_ids,
            resource=request.resource,
            action=request.action,
            environment=request.environment,
            incident_id=request.incident_id,
            severity=request.severity,
        )

        raw = self._engine.evaluate(context)
        decision = self._finalize(raw, request, context)
        self._ledger.append(decision, fingerprint=fingerprint)
        return decision

    # -- helpers ---------------------------------------------------------
    def _reuse_conflict(self, request: GovernanceRequest) -> GovernanceDecision:
        return GovernanceDecision(
            effect=DecisionEffect.DENY,
            reason="request id reuse conflict",
            reason_code=ReasonCode.REQUEST_ID_REUSE_CONFLICT.value,
            request_id=request.request_id,
            principal_id=request.principal_id,
            resource=request.resource,
            action=request.action,
            decided_at=datetime.now(timezone.utc),
        )

    def _finalize(
        self,
        raw: GovernanceDecision,
        request: GovernanceRequest,
        context: GovernanceContext,
    ) -> GovernanceDecision:
        sequence = self._ledger.next_sequence()
        return GovernanceDecision(
            effect=raw.effect,
            reason=raw.reason,
            policy_id=raw.policy_id,
            approval_required=raw.approval_required,
            decision_id=f"DEC-{uuid.uuid4().hex[:12].upper()}",
            request_id=request.request_id,
            principal_id=request.principal_id,
            resource=request.resource,
            action=request.action,
            authority_source=self._resolve_authority_source(request, context),
            reason_code=_reason_code_for(raw.effect),
            decided_at=datetime.now(timezone.utc),
            sequence=sequence,
            context_hash=request.context_hash,
        )

    def _resolve_authority_source(
        self,
        request: GovernanceRequest,
        context: GovernanceContext,
    ) -> str | None:
        if self._authority_resolver is None:
            return None
        authorities = self._authority_resolver.resolve(
            request.principal_id,
            request.resource,
            request.action,
            roles=context.role_ids,
        )
        if not authorities:
            return None
        return authorities[0].source
