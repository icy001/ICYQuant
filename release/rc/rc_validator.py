"""
Release candidate validation gates.

Validates release candidates before promotion by checking:
tests pass, benchmark meets SLA, security scan clean, API compatibility
confirmed, documentation complete, and rollback plan verified.

Supports validation gates between Alpha → Beta → RC → GA.

Usage::

    validator = RCValidator()
    result = validator.validate(rc, target_stage="beta")
    if result.promotion_recommended:
        rc.promote("beta")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .release_candidate import RCStage, RCStatus


class ValidationGate(str, Enum):
    """Validation gate identifiers."""

    TESTS = "tests"
    BENCHMARK = "benchmark"
    SECURITY_SCAN = "security_scan"
    API_COMPATIBILITY = "api_compatibility"
    DOCUMENTATION = "documentation"
    ROLLBACK_PLAN = "rollback_plan"


class GateStatus(str, Enum):
    """Status of a single validation gate."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


# Required gates for each promotion path
_GATE_REQUIREMENTS: Dict[str, List[ValidationGate]] = {
    "alpha->beta": [
        ValidationGate.TESTS,
        ValidationGate.BENCHMARK,
    ],
    "beta->rc": [
        ValidationGate.TESTS,
        ValidationGate.BENCHMARK,
        ValidationGate.SECURITY_SCAN,
        ValidationGate.API_COMPATIBILITY,
    ],
    "rc->ga": [
        ValidationGate.TESTS,
        ValidationGate.BENCHMARK,
        ValidationGate.SECURITY_SCAN,
        ValidationGate.API_COMPATIBILITY,
        ValidationGate.DOCUMENTATION,
        ValidationGate.ROLLBACK_PLAN,
    ],
}

# Stage ordering for path construction
_STAGE_ORDER: List[RCStage] = [
    RCStage.ALPHA,
    RCStage.BETA,
    RCStage.RC,
    RCStage.GA,
]


@dataclass
class GateResult:
    """Result of a single validation gate.

    Attributes:
        gate: The validation gate identifier.
        status: Gate outcome status.
        message: Human-readable result summary.
        details: Arbitrary details about the gate execution.
        executed_at: Timestamp when the gate was evaluated.
    """

    gate: ValidationGate = ValidationGate.TESTS
    status: GateStatus = GateStatus.FAIL
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class RCValidationResult:
    """Aggregated validation result for a release candidate.

    Attributes:
        version: The version string that was validated.
        target_stage: The stage being promoted to.
        source_stage: The current stage before validation.
        gate_results: Per-gate validation results.
        all_passed: True if all required gates passed.
        has_warnings: True if any gate has warnings.
        promotion_recommended: True if promotion should proceed.
        summary: Overall summary message.
        validated_at: Timestamp of validation.
    """

    version: str = ""
    target_stage: RCStage = RCStage.ALPHA
    source_stage: RCStage = RCStage.ALPHA
    gate_results: List[GateResult] = field(default_factory=list)
    all_passed: bool = False
    has_warnings: bool = False
    promotion_recommended: bool = False
    summary: str = ""
    validated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def get_gate_status(self, gate: ValidationGate) -> Optional[GateStatus]:
        """Get the status of a specific gate.

        Args:
            gate: The validation gate to look up.

        Returns:
            GateStatus if found, None otherwise.
        """
        for result in self.gate_results:
            if result.gate == gate:
                return result.status
        return None

    def get_failed_gates(self) -> List[GateResult]:
        """Return all gates that failed.

        Returns:
            List of failed GateResult objects.
        """
        return [g for g in self.gate_results if g.status == GateStatus.FAIL]

    def get_warning_gates(self) -> List[GateResult]:
        """Return all gates that have warnings.

        Returns:
            List of warning GateResult objects.
        """
        return [g for g in self.gate_results if g.status == GateStatus.WARN]


class RCValidator:
    """Release candidate validator for promotion gates.

    Evaluates validation gates between lifecycle stages (Alpha → Beta → RC → GA)
    and provides a promotion recommendation based on gate outcomes.

    Each gate is evaluated by a pluggable check function that the caller provides.
    Gate functions return a GateResult or a boolean with an optional message.

    Usage::

        validator = RCValidator()
        validator.register_check(ValidationGate.TESTS, my_test_runner)
        validator.register_check(ValidationGate.SECURITY_SCAN, my_security_scanner)
        result = validator.validate(rc, target_stage="rc")
        if result.promotion_recommended:
            rc.promote("rc")
    """

    def __init__(self):
        """Initialize the validator with no registered checks."""
        self._checks: Dict[ValidationGate, Callable[..., Any]] = {}

    def register_check(
        self,
        gate: ValidationGate,
        check_fn: Callable[..., Any],
    ) -> None:
        """Register a check function for a validation gate.

        The check function should accept any arguments and return either:
        - A GateResult instance
        - A bool (True = PASS, False = FAIL)
        - A tuple of (bool, str) for status + message

        Args:
            gate: The validation gate this check applies to.
            check_fn: Callable that evaluates the gate.
        """
        self._checks[gate] = check_fn

    def validate(
        self,
        status: RCStatus,
        target_stage: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RCValidationResult:
        """Validate a release candidate for promotion to the target stage.

        Args:
            status: Current RCStatus of the release candidate.
            target_stage: Target stage to validate promotion for.
            context: Optional context dict passed to check functions.

        Returns:
            RCValidationResult with per-gate results and promotion recommendation.
        """
        target = RCStage(target_stage.lower())
        source = status.current_stage
        path = self._construct_path(source, target)
        required_gates = self._get_required_gates(path)

        gate_results: List[GateResult] = []
        context = context or {}
        context["status"] = status
        context["target_stage"] = target

        for gate in required_gates:
            result = self._evaluate_gate(gate, context)
            gate_results.append(result)

        all_passed = all(
            g.status in (GateStatus.PASS, GateStatus.SKIP) for g in gate_results
        )
        has_warnings = any(g.status == GateStatus.WARN for g in gate_results)
        promotion_recommended = all_passed and status.blocking_issues == []

        summary = self._build_summary(
            gate_results, all_passed, has_warnings, promotion_recommended
        )

        return RCValidationResult(
            version=status.version,
            target_stage=target,
            source_stage=source,
            gate_results=gate_results,
            all_passed=all_passed,
            has_warnings=has_warnings,
            promotion_recommended=promotion_recommended,
            summary=summary,
        )

    def validate_gate(
        self,
        gate: ValidationGate,
        context: Optional[Dict[str, Any]] = None,
    ) -> GateResult:
        """Validate a single gate.

        Args:
            gate: The validation gate to evaluate.
            context: Optional context dict passed to the check function.

        Returns:
            GateResult for the specified gate.
        """
        return self._evaluate_gate(gate, context or {})

    def is_gate_registered(self, gate: ValidationGate) -> bool:
        """Check if a check function is registered for a gate.

        Args:
            gate: The validation gate to check.

        Returns:
            True if a check function is registered.
        """
        return gate in self._checks

    def _construct_path(
        self,
        source: RCStage,
        target: RCStage,
    ) -> str:
        """Construct the promotion path key.

        Args:
            source: Current stage.
            target: Target stage.

        Returns:
            Path key (e.g., "alpha->beta", "beta->rc", "rc->ga").

        Raises:
            ValueError: If the transition is not supported.
        """
        source_idx = _STAGE_ORDER.index(source) if source in _STAGE_ORDER else -1
        target_idx = _STAGE_ORDER.index(target) if target in _STAGE_ORDER else -1

        if source_idx < 0 or target_idx < 0:
            raise ValueError(
                f"Unknown stage: {source.value} → {target.value}"
            )

        if target_idx <= source_idx:
            raise ValueError(
                f"Target stage {target.value} must be after source stage {source.value}"
            )

        path = f"{source.value}->{target.value}"
        return path

    def _get_required_gates(self, path: str) -> List[ValidationGate]:
        """Get the list of required gates for a promotion path.

        If a specific path is not configured, the gates for the longest
        matching prefix path are returned.

        Args:
            path: Promotion path key (e.g., "beta->rc").

        Returns:
            List of required ValidationGate entries.
        """
        if path in _GATE_REQUIREMENTS:
            return list(_GATE_REQUIREMENTS[path])

        parts = path.split("->")
        source = parts[0]
        target = parts[1]

        for key, gates in _GATE_REQUIREMENTS.items():
            key_parts = key.split("->")
            if key_parts[0] == source:
                if target == key_parts[1] or (
                    _STAGE_ORDER.index(RCStage(target))
                    > _STAGE_ORDER.index(RCStage(key_parts[1]))
                ):
                    return list(gates)

        return list(_GATE_REQUIREMENTS.get("alpha->beta", []))

    def _evaluate_gate(
        self,
        gate: ValidationGate,
        context: Dict[str, Any],
    ) -> GateResult:
        """Evaluate a single validation gate.

        Args:
            gate: The gate to evaluate.
            context: Context dictionary for the check function.

        Returns:
            GateResult with the outcome.
        """
        if gate not in self._checks:
            return GateResult(
                gate=gate,
                status=GateStatus.SKIP,
                message=f"No check registered for gate: {gate.value}",
            )

        check_fn = self._checks[gate]
        try:
            outcome = check_fn(context)

            if isinstance(outcome, GateResult):
                return outcome

            if isinstance(outcome, bool):
                return GateResult(
                    gate=gate,
                    status=GateStatus.PASS if outcome else GateStatus.FAIL,
                    message=f"{gate.value}: {'passed' if outcome else 'failed'}",
                )

            if isinstance(outcome, tuple) and len(outcome) >= 2:
                passed = bool(outcome[0])
                message = str(outcome[1])
                gate_status = GateStatus.PASS if passed else GateStatus.FAIL
                details = outcome[2] if len(outcome) > 2 and isinstance(outcome[2], dict) else {}
                return GateResult(
                    gate=gate,
                    status=gate_status,
                    message=message,
                    details=details,
                )

            return GateResult(
                gate=gate,
                status=GateStatus.WARN,
                message=f"Unexpected return type from {gate.value} check: {type(outcome).__name__}",
            )
        except Exception as exc:
            return GateResult(
                gate=gate,
                status=GateStatus.FAIL,
                message=f"Gate check raised exception: {exc}",
                details={"exception": str(exc)},
            )

    @staticmethod
    def _build_summary(
        gate_results: List[GateResult],
        all_passed: bool,
        has_warnings: bool,
        promotion_recommended: bool,
    ) -> str:
        """Build a human-readable summary of validation results.

        Args:
            gate_results: Per-gate results.
            all_passed: Whether all gates passed.
            has_warnings: Whether any gate has warnings.
            promotion_recommended: Whether promotion is recommended.

        Returns:
            Summary string.
        """
        total = len(gate_results)
        passed = sum(1 for g in gate_results if g.status == GateStatus.PASS)
        failed = sum(1 for g in gate_results if g.status == GateStatus.FAIL)
        warnings = sum(1 for g in gate_results if g.status == GateStatus.WARN)
        skipped = sum(1 for g in gate_results if g.status == GateStatus.SKIP)

        parts: List[str] = [f"{passed}/{total} gates passed"]
        if failed:
            parts.append(f"{failed} failed")
        if warnings:
            parts.append(f"{warnings} warnings")
        if skipped:
            parts.append(f"{skipped} skipped")

        if promotion_recommended:
            parts.append("Promotion RECOMMENDED")
        elif all_passed:
            parts.append("Promotion NOT recommended (blocking issues may exist)")
        else:
            parts.append("Promotion BLOCKED")

        return " | ".join(parts)