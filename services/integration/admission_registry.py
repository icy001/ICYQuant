"""AdmissionRegistry — tracks all admission results for audit and retrieval."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .admission_result import AdmissionResult, AdmissionResultStatus
from .order_certificate import OrderCertificate


@dataclass
class AdmissionRecord:
    """A record of a single admission."""
    flow_id: str = ""
    intent_id: str = ""
    result: Optional[AdmissionResult] = None
    certificate: Optional[OrderCertificate] = None
    recorded_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "intent_id": self.intent_id,
            "result": self.result.to_dict() if self.result else None,
            "certificate": self.certificate.to_dict() if self.certificate else None,
            "recorded_at": self.recorded_at,
        }


@dataclass
class AdmissionRegistry:
    """Tracks all admission results.

    Provides lookup by flow_id, intent_id, and certificate_id for
    audit and downstream consumption (OMS, execution).
    """

    _records: Dict[str, AdmissionRecord] = field(default_factory=dict, repr=False)
    _by_certificate: Dict[str, str] = field(default_factory=dict, repr=False)

    def register(
        self,
        flow_id: str,
        intent_id: str,
        result: AdmissionResult,
        certificate: Optional[OrderCertificate] = None,
    ) -> AdmissionRecord:
        """Record an admission result."""
        record = AdmissionRecord(
            flow_id=flow_id,
            intent_id=intent_id,
            result=result,
            certificate=certificate,
        )
        self._records[flow_id] = record
        if certificate:
            self._by_certificate[certificate.certificate_id] = flow_id
        return record

    def get_by_flow(self, flow_id: str) -> Optional[AdmissionRecord]:
        """Retrieve admission record by flow_id."""
        return self._records.get(flow_id)

    def get_by_certificate(self, certificate_id: str) -> Optional[AdmissionRecord]:
        """Retrieve admission record by certificate_id."""
        flow_id = self._by_certificate.get(certificate_id)
        if flow_id:
            return self._records.get(flow_id)
        return None

    def is_admitted(self, flow_id: str) -> bool:
        """Check if a flow has been admitted."""
        record = self._records.get(flow_id)
        if not record or not record.result:
            return False
        return record.result.status == AdmissionResultStatus.ADMITTED

    def list_admitted(self) -> List[AdmissionRecord]:
        """List all admitted orders."""
        return [
            r for r in self._records.values()
            if r.result and r.result.status == AdmissionResultStatus.ADMITTED
        ]

    def list_by_status(self, status: AdmissionResultStatus) -> List[AdmissionRecord]:
        """List all records with a given status."""
        return [
            r for r in self._records.values()
            if r.result and r.result.status == status
        ]

    def count(self) -> int:
        """Total number of admission records."""
        return len(self._records)

    def reset(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()
        self._by_certificate.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": len(self._records),
            "admitted": len(self.list_admitted()),
            "rejected": len(self.list_by_status(AdmissionResultStatus.REJECTED)),
            "blocked": len(self.list_by_status(AdmissionResultStatus.BLOCKED)),
        }

    def __repr__(self) -> str:
        return f"AdmissionRegistry(records={len(self._records)})"
