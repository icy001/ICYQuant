"""Compliance Validator – validates decisions against risk, exposure, and regulatory rules."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComplianceStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


@dataclass
class ComplianceResult:
    status: ComplianceStatus
    rule_name: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class ComplianceValidator:
    """Validates trading decisions against compliance and regulatory rules."""

    def __init__(self) -> None:
        self._rules: List[Dict[str, Any]] = []
        self._results: List[ComplianceResult] = []

    def validate(self, approved: bool) -> bool:
        """Basic compliance check.

        Args:
            approved: whether the decision is approved by compliance.

        Returns:
            True if approved.
        """
        return approved

    def check_risk_limit(self, exposure: float, max_exposure: float) -> ComplianceResult:
        """Check if exposure is within limits."""
        ok = exposure <= max_exposure
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="risk_limit",
            message=f"Exposure {exposure} vs limit {max_exposure}",
            details={"exposure": exposure, "limit": max_exposure},
        )

    def check_exposure(self, current: float, limit: float, symbol: str = "") -> ComplianceResult:
        """Check per-symbol or total exposure."""
        ok = current <= limit
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="exposure_check",
            message=f"{symbol} exposure {current} vs limit {limit}" if symbol else f"Exposure {current} vs limit {limit}",
            details={"current": current, "limit": limit, "symbol": symbol},
        )

    def check_trading_rules(self, signal: str, allowed_signals: List[str]) -> ComplianceResult:
        """Verify the signal is in the allowed set."""
        ok = signal in allowed_signals
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="trading_rules",
            message=f"Signal '{signal}' allowed: {ok}",
            details={"signal": signal, "allowed": allowed_signals},
        )

    def check_blacklist(self, symbol: str, blacklist: List[str]) -> ComplianceResult:
        """Check if symbol is on the blacklist."""
        ok = symbol not in blacklist
        return ComplianceResult(
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            rule_name="blacklist",
            message=f"Symbol '{symbol}' blacklisted: {not ok}",
            details={"symbol": symbol, "blacklisted": not ok},
        )

    def validate_all(self, results: List[ComplianceResult]) -> ComplianceResult:
        """Aggregate multiple compliance checks into one result."""
        if not results:
            return ComplianceResult(
                status=ComplianceStatus.PASS,
                rule_name="all_checks",
                message="No rules to validate",
            )

        failures = [r for r in results if r.status == ComplianceStatus.FAIL]
        reviews = [r for r in results if r.status == ComplianceStatus.REVIEW]

        if failures:
            return ComplianceResult(
                status=ComplianceStatus.FAIL,
                rule_name="multi_check",
                message=f"{len(failures)} rule(s) failed: {', '.join(r.rule_name for r in failures)}",
                details={"passed": len(results) - len(failures) - len(reviews), "failed": len(failures), "review": len(reviews)},
            )
        if reviews:
            return ComplianceResult(
                status=ComplianceStatus.REVIEW,
                rule_name="multi_check",
                message=f"{len(reviews)} rule(s) require review",
                details={"passed": len(results) - len(reviews), "review": len(reviews)},
            )

        return ComplianceResult(
            status=ComplianceStatus.PASS,
            rule_name="multi_check",
            message=f"All {len(results)} rules passed",
            details={"passed": len(results)},
        )
