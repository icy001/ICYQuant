"""
In-memory implementation of ``RiskDecisionRepository`` (Commit 41 Part 1.2).

This is a test / local implementation only.  Production deployments switch
to a durable backend (e.g. PostgreSQL) behind the same port.
"""

from __future__ import annotations

from ...decision.decision_record import RiskDecisionRecord
from ...policy_trace import RiskPolicyTrace


class InMemoryRiskDecisionRepository:
    """Simple in-memory store enforcing one record per ``request_id``."""

    def __init__(self) -> None:
        self._records_by_decision_id: dict[str, RiskDecisionRecord] = {}
        self._decision_id_by_request_id: dict[str, str] = {}

    def save(self, record: RiskDecisionRecord) -> None:
        existing = self.get_by_request_id(record.request_id)

        if existing is not None:
            if existing.decision_id != record.decision_id:
                raise ValueError(
                    "risk decision request already exists"
                )

            return

        self._records_by_decision_id[record.decision_id] = record
        self._decision_id_by_request_id[record.request_id] = record.decision_id

    def get_by_decision_id(self, decision_id: str) -> RiskDecisionRecord | None:
        return self._records_by_decision_id.get(decision_id)

    def get_by_request_id(self, request_id: str) -> RiskDecisionRecord | None:
        decision_id = self._decision_id_by_request_id.get(request_id)
        if decision_id is None:
            return None
        return self._records_by_decision_id.get(decision_id)

    def get_policy_trace(self, decision_id: str) -> RiskPolicyTrace | None:
        record = self._records_by_decision_id.get(decision_id)
        if record is None:
            return None
        return record.policy_trace
