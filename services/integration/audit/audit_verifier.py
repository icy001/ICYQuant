"""Audit Verifier — end-to-end audit verification.

Combines chain integrity, fingerprint checks, append-only enforcement,
and event coverage into a single audit verification pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit_event import AuditEvent, EventType
from .audit_record import AuditRecord
from .audit_chain import AuditChain, AuditChainIntegrityReport
from .audit_fingerprint import AuditFingerprint


@dataclass
class AuditVerificationReport:
    """Full audit verification result."""

    passed: bool = True
    record_id: str = ""
    lineage_id: str = ""

    chain_report: AuditChainIntegrityReport | None = None
    fingerprint_valid: bool = True
    append_only_valid: bool = True
    coverage_issues: list[str] = field(default_factory=list)
    overwrite_detected: list[str] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "record_id": self.record_id,
            "lineage_id": self.lineage_id,
            "fingerprint_valid": self.fingerprint_valid,
            "append_only_valid": self.append_only_valid,
            "coverage_issues": list(self.coverage_issues),
            "overwrite_detected": list(self.overwrite_detected),
            "errors": list(self.errors),
        }


# Expected control events that should appear in every complete lineage
REQUIRED_CONTROL_EVENTS: list[EventType] = [
    EventType.DECISION_CREATED,
    EventType.RISK_EVALUATED,
    EventType.GOVERNANCE_EVALUATED,
    EventType.AUTHORITY_CHECKED,
    EventType.APPROVAL_GRANTED,
    EventType.CERTIFICATE_ISSUED,
    EventType.ORDER_CREATED,
]


@dataclass
class AuditVerifier:
    """End-to-end audit verification for a control lineage.

    Validates:
    - Hash chain integrity (every event links correctly)
    - Fingerprint consistency (frozen snapshot matches current state)
    - Append-only enforcement (no in-place modification)
    - Coverage (all required control events are present)
    """

    _chain: AuditChain = field(default_factory=AuditChain)

    # ── Registration ──────────────────────────────────────────────

    def register_record(self, record: AuditRecord) -> None:
        self._chain._records[record.record_id] = record

    # ── Main verification ─────────────────────────────────────────

    def verify(self, record: AuditRecord,
               expected_fingerprint: AuditFingerprint | None = None,
               ) -> AuditVerificationReport:
        """Perform full audit verification on a record."""
        report = AuditVerificationReport(
            record_id=record.record_id,
            lineage_id=record.lineage_id,
        )

        # 1. Chain integrity
        chain_report = self._chain.verify_chain(record)
        report.chain_report = chain_report
        if not chain_report.valid:
            report.passed = False
            report.errors.extend(chain_report.errors)

        # 2. Fingerprint check
        if expected_fingerprint is not None:
            report.fingerprint_valid = expected_fingerprint.verify(record)
            if not report.fingerprint_valid:
                report.add_error(
                    "Audit fingerprint mismatch — record may have been tampered"
                )

        # 3. Append-only (no in-place modification)
        overwrites = self._detect_overwrites(record)
        if overwrites:
            report.overwrite_detected = overwrites
            report.append_only_valid = False
            report.add_error(
                f"Append-only violation detected: {len(overwrites)} overwrite(s)"
            )

        # 4. Coverage check
        coverage = self._check_coverage(record)
        if coverage:
            report.coverage_issues = coverage
            report.add_error(
                f"Missing required events: {', '.join(coverage)}"
            )

        return report

    # ── Detection helpers ─────────────────────────────────────────

    def _detect_overwrites(self, record: AuditRecord) -> list[str]:
        """Check for events with same ID but different content."""
        seen: dict[str, str] = {}
        overwrites: list[str] = []
        for e in record.events:
            if e.event_id in seen:
                if e.event_hash != seen[e.event_id]:
                    overwrites.append(e.event_id)
            else:
                seen[e.event_id] = e.event_hash
        return overwrites

    def _check_coverage(self, record: AuditRecord) -> list[str]:
        """Check which required control events are missing."""
        present = {e.event_type for e in record.events}
        missing: list[str] = []
        for req in REQUIRED_CONTROL_EVENTS:
            if req not in present:
                missing.append(req.name)
        return missing
