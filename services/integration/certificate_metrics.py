"""CertificateMetrics — observability for certificate lifecycle operations.

Tracks:
- Issuance rates and trends
- Usage/consumption patterns
- Revocation rates and reasons
- Expiry rates
- Replay detection events
- Verification pass/fail rates
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CertificateMetrics:
    """Tracks operational metrics for the certificate system."""

    # ── Counters ──────────────────────────────────────────────
    issued_count: int = 0
    sealed_count: int = 0
    verified_count: int = 0
    verified_pass: int = 0
    verified_fail: int = 0
    used_count: int = 0
    revoked_count: int = 0
    expired_count: int = 0
    replay_detected: int = 0
    integrity_failures: int = 0

    # ── Consumption tracking ──────────────────────────────────
    total_quantity_issued: float = 0.0
    total_quantity_consumed: float = 0.0
    total_notional_issued: float = 0.0
    total_notional_consumed: float = 0.0

    # ── Revocation reasons ────────────────────────────────────
    revocation_reasons: Dict[str, int] = field(default_factory=dict)

    # ── Timing ────────────────────────────────────────────────
    build_times: List[float] = field(default_factory=list)
    seal_times: List[float] = field(default_factory=list)

    # ── Event recording methods ───────────────────────────────

    def record_issued(self) -> None:
        self.issued_count += 1

    def record_sealed(self, duration: float = 0.0) -> None:
        self.sealed_count += 1
        if duration > 0:
            self.seal_times.append(duration)

    def record_verification(self, passed: bool) -> None:
        self.verified_count += 1
        if passed:
            self.verified_pass += 1
        else:
            self.verified_fail += 1

    def record_used(
        self, quantity: float = 0.0, notional: float = 0.0
    ) -> None:
        self.used_count += 1
        self.total_quantity_consumed += quantity
        self.total_notional_consumed += notional

    def record_revoked(self, reason: str = "") -> None:
        self.revoked_count += 1
        key = reason or "UNKNOWN"
        self.revocation_reasons[key] = (
            self.revocation_reasons.get(key, 0) + 1
        )

    def record_expired(self) -> None:
        self.expired_count += 1

    def record_replay(self) -> None:
        self.replay_detected += 1

    def record_integrity_failure(self) -> None:
        self.integrity_failures += 1

    def record_quantity_issued(self, quantity: float) -> None:
        self.total_quantity_issued += quantity

    def record_notional_issued(self, notional: float) -> None:
        self.total_notional_issued += notional

    # ── Derived metrics ───────────────────────────────────────

    @property
    def verification_pass_rate(self) -> float:
        """Pass rate for certificate verifications."""
        if self.verified_count == 0:
            return 1.0
        return self.verified_pass / self.verified_count

    @property
    def revocation_rate(self) -> float:
        """Revocation rate relative to issued."""
        if self.issued_count == 0:
            return 0.0
        return self.revoked_count / self.issued_count

    @property
    def avg_build_time_ms(self) -> float:
        """Average certificate build time in milliseconds."""
        times = self.build_times
        if not times:
            return 0.0
        return (sum(times) / len(times)) * 1000.0

    @property
    def avg_seal_time_ms(self) -> float:
        """Average seal time in milliseconds."""
        times = self.seal_times
        if not times:
            return 0.0
        return (sum(times) / len(times)) * 1000.0

    @property
    def quantity_consumption_rate(self) -> float:
        """Fraction of issued quantity that has been consumed."""
        if self.total_quantity_issued == 0:
            return 0.0
        return self.total_quantity_consumed / self.total_quantity_issued

    @property
    def notional_consumption_rate(self) -> float:
        """Fraction of issued notional that has been consumed."""
        if self.total_notional_issued == 0:
            return 0.0
        return self.total_notional_consumed / self.total_notional_issued

    # ── Reset ─────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.issued_count = 0
        self.sealed_count = 0
        self.verified_count = 0
        self.verified_pass = 0
        self.verified_fail = 0
        self.used_count = 0
        self.revoked_count = 0
        self.expired_count = 0
        self.replay_detected = 0
        self.integrity_failures = 0
        self.total_quantity_issued = 0.0
        self.total_quantity_consumed = 0.0
        self.total_notional_issued = 0.0
        self.total_notional_consumed = 0.0
        self.revocation_reasons.clear()
        self.build_times.clear()
        self.seal_times.clear()

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issued_count": self.issued_count,
            "sealed_count": self.sealed_count,
            "verified_count": self.verified_count,
            "verified_pass": self.verified_pass,
            "verified_fail": self.verified_fail,
            "verification_pass_rate": self.verification_pass_rate,
            "used_count": self.used_count,
            "revoked_count": self.revoked_count,
            "revocation_rate": self.revocation_rate,
            "revocation_reasons": self.revocation_reasons,
            "expired_count": self.expired_count,
            "replay_detected": self.replay_detected,
            "integrity_failures": self.integrity_failures,
            "total_quantity_issued": self.total_quantity_issued,
            "total_quantity_consumed": self.total_quantity_consumed,
            "total_notional_issued": self.total_notional_issued,
            "total_notional_consumed": self.total_notional_consumed,
            "quantity_consumption_rate": self.quantity_consumption_rate,
            "notional_consumption_rate": self.notional_consumption_rate,
            "avg_build_time_ms": self.avg_build_time_ms,
            "avg_seal_time_ms": self.avg_seal_time_ms,
        }

    def __repr__(self) -> str:
        return (
            f"CertificateMetrics(issued={self.issued_count}, "
            f"verified={self.verified_count}, "
            f"used={self.used_count}, "
            f"revoked={self.revoked_count}, "
            f"replay={self.replay_detected})"
        )
