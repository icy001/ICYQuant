"""
Signal Validator — Multi-stage validation for trading signals.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Validation pipeline:
    Direction → Market Status → Trading Hours → Liquidity → Risk Rule → Valid Signal

Filters out anomalous or invalid signals before they reach downstream consumers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, time
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal, SignalDirection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ValidationStage(str, Enum):
    DIRECTION = "direction"
    INSTRUMENT = "instrument"
    MARKET_STATUS = "market_status"
    TRADING_HOURS = "trading_hours"
    LIQUIDITY = "liquidity"
    RISK_RULE = "risk_rule"
    CONFIDENCE = "confidence"
    DUPLICATE = "duplicate"


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"      # Hard failure — signal is invalid
    WARNING = "WARNING"  # Soft failure — signal may be degraded
    INFO = "INFO"        # Informational only


@dataclass
class ValidationIssue:
    """A single validation finding."""
    stage: ValidationStage
    severity: ValidationSeverity
    message: str
    detail: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of signal validation."""
    signal_id: str
    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    stages_run: List[ValidationStage] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


# ---------------------------------------------------------------------------
# Signal Validator
# ---------------------------------------------------------------------------

class SignalValidator:
    """Multi-stage signal validation engine.

    Each stage can be enabled/disabled. A signal must pass all ERROR-level
    checks to be considered valid. WARNING-level issues are informational.
    """

    def __init__(self):
        self._stages_enabled: Dict[ValidationStage, bool] = {
            ValidationStage.DIRECTION: True,
            ValidationStage.INSTRUMENT: True,
            ValidationStage.MARKET_STATUS: True,
            ValidationStage.TRADING_HOURS: True,
            ValidationStage.LIQUIDITY: False,  # Optional, requires market data
            ValidationStage.RISK_RULE: False,   # Optional, requires risk engine
            ValidationStage.CONFIDENCE: True,
            ValidationStage.DUPLICATE: True,
        }

        # Recently seen signal hashes for duplicate detection
        self._recent_hashes: Dict[str, datetime] = {}
        self._duplicate_window_seconds: float = 60.0

    # ------------------------------------------------------------------
    # Main Validation
    # ------------------------------------------------------------------

    async def validate(self, signal: Signal) -> ValidationResult:
        """Run all enabled validation stages against a signal."""
        result = ValidationResult(signal_id=signal.signal_id)

        stages = [
            (ValidationStage.DIRECTION, self._validate_direction),
            (ValidationStage.INSTRUMENT, self._validate_instrument),
            (ValidationStage.MARKET_STATUS, self._validate_market_status),
            (ValidationStage.TRADING_HOURS, self._validate_trading_hours),
            (ValidationStage.LIQUIDITY, self._validate_liquidity),
            (ValidationStage.RISK_RULE, self._validate_risk_rule),
            (ValidationStage.CONFIDENCE, self._validate_confidence),
            (ValidationStage.DUPLICATE, self._validate_duplicate),
        ]

        for stage, validator_fn in stages:
            if not self._stages_enabled.get(stage, False):
                continue
            result.stages_run.append(stage)
            issues = await validator_fn(signal)
            result.issues.extend(issues)
            # Fail fast on first ERROR
            if any(i.severity == ValidationSeverity.ERROR for i in issues):
                result.passed = False
                break

        if result.passed:
            logger.debug("Signal %s passed validation", signal.signal_id)
        else:
            error_msgs = [e.message for e in result.errors]
            logger.info("Signal %s failed validation: %s", signal.signal_id, "; ".join(error_msgs))

        return result

    # ------------------------------------------------------------------
    # Validation Stages
    # ------------------------------------------------------------------

    async def _validate_direction(self, signal: Signal) -> List[ValidationIssue]:
        """Validate that direction is a valid enum value."""
        issues = []
        if not isinstance(signal.direction, SignalDirection):
            issues.append(ValidationIssue(
                stage=ValidationStage.DIRECTION,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid direction: {signal.direction}",
            ))
        elif signal.direction not in (SignalDirection.LONG, SignalDirection.SHORT, SignalDirection.FLAT):
            issues.append(ValidationIssue(
                stage=ValidationStage.DIRECTION,
                severity=ValidationSeverity.ERROR,
                message=f"Unknown direction: {signal.direction.value}",
            ))
        return issues

    async def _validate_instrument(self, signal: Signal) -> List[ValidationIssue]:
        """Validate that instrument identifier is present."""
        issues = []
        if not signal.instrument or not signal.instrument.strip():
            issues.append(ValidationIssue(
                stage=ValidationStage.INSTRUMENT,
                severity=ValidationSeverity.ERROR,
                message="Instrument identifier is empty",
            ))
        return issues

    async def _validate_market_status(self, signal: Signal) -> List[ValidationIssue]:
        """Validate that the market for this instrument is open/available."""
        # Placeholder: in production, check against market calendar
        return []

    async def _validate_trading_hours(self, signal: Signal) -> List[ValidationIssue]:
        """Validate signal is generated within trading hours."""
        issues = []
        market_session = signal.metadata.get("market_session", "REGULAR")
        if market_session == "CLOSED":
            issues.append(ValidationIssue(
                stage=ValidationStage.TRADING_HOURS,
                severity=ValidationSeverity.WARNING,
                message="Signal generated outside trading hours",
                detail=f"Market session: {market_session}",
            ))
        return issues

    async def _validate_liquidity(self, signal: Signal) -> List[ValidationIssue]:
        """Validate instrument has sufficient liquidity (optional stage)."""
        # Placeholder: in production, check liquidity metrics
        return []

    async def _validate_risk_rule(self, signal: Signal) -> List[ValidationIssue]:
        """Validate against risk rules (optional stage)."""
        # Placeholder: in production, check risk limits
        return []

    async def _validate_confidence(self, signal: Signal) -> List[ValidationIssue]:
        """Validate confidence is within [0, 1] range."""
        issues = []
        if signal.confidence < 0.0 or signal.confidence > 1.0:
            issues.append(ValidationIssue(
                stage=ValidationStage.CONFIDENCE,
                severity=ValidationSeverity.ERROR,
                message=f"Confidence out of range: {signal.confidence}",
                detail="Must be in [0.0, 1.0]",
            ))
        return issues

    async def _validate_duplicate(self, signal: Signal) -> List[ValidationIssue]:
        """Detect duplicate signals within a short time window."""
        issues = []
        key = f"{signal.strategy_id}:{signal.instrument}:{signal.direction.value}"
        last_seen = self._recent_hashes.get(key)

        now = datetime.now(timezone.utc)
        if last_seen and (now - last_seen).total_seconds() < self._duplicate_window_seconds:
            issues.append(ValidationIssue(
                stage=ValidationStage.DUPLICATE,
                severity=ValidationSeverity.WARNING,
                message="Duplicate signal detected within window",
                detail=f"Last seen {(now - last_seen).total_seconds():.1f}s ago",
            ))

        self._recent_hashes[key] = now
        # Prune old entries
        self._prune_hashes(now)

        return issues

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def enable_stage(self, stage: ValidationStage) -> None:
        self._stages_enabled[stage] = True

    def disable_stage(self, stage: ValidationStage) -> None:
        self._stages_enabled[stage] = False

    def set_duplicate_window(self, seconds: float) -> None:
        self._duplicate_window_seconds = seconds

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prune_hashes(self, now: datetime) -> None:
        """Remove hash entries older than the duplicate window."""
        cutoff = now.timestamp() - self._duplicate_window_seconds * 2
        expired = [k for k, v in self._recent_hashes.items() if v.timestamp() < cutoff]
        for k in expired:
            del self._recent_hashes[k]
