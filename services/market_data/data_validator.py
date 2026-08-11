"""
Data Validator — comprehensive market data validation engine with
configurable validation rules and severity levels.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional

from .canonical_model import CanonicalMarketData

logger = logging.getLogger(__name__)


class ValidationRuleType(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    TIMESTAMP = "timestamp"
    SYMBOL = "symbol"
    SPREAD = "spread"
    ARBITRAGE = "arbitrage"
    CUSTOM = "custom"


@dataclass
class ValidationRule:
    """A single validation rule."""

    rule_id: str = ""
    rule_type: ValidationRuleType = ValidationRuleType.CUSTOM
    description: str = ""
    severity: str = "error"  # error, warning, info
    is_enabled: bool = True
    check_fn: Optional[Callable] = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataValidationError:
    """A data validation error/warning."""

    rule_id: str = ""
    rule_type: ValidationRuleType = ValidationRuleType.CUSTOM
    message: str = ""
    severity: str = "error"
    field: str = ""
    value: Any = None
    threshold: Any = None
    timestamp_ns: int = 0


@dataclass
class DataValidationReport:
    """Result of data validation."""

    is_valid: bool = True
    instrument_id: str = ""
    event_type: str = ""
    errors: list[DataValidationError] = field(default_factory=list)
    warnings: list[DataValidationError] = field(default_factory=list)
    rule_results: dict[str, bool] = field(default_factory=dict)
    validated_at: Optional[datetime] = None
    duration_us: float = 0.0


class DataValidator:
    """
    Comprehensive market data validation engine.

    Built-in rules:
    - Price non-negative
    - Bid <= Ask (no negative spread)
    - Volume non-negative
    - Timestamp not in future
    - Symbol format validation
    - Cross-field consistency
    """

    def __init__(self) -> None:
        self._rules: dict[str, ValidationRule] = {}
        self._stats: dict[str, int] = {"total_validated": 0, "total_errors": 0, "total_warnings": 0}
        self._register_builtin_rules()

    async def initialize(self) -> None:
        logger.info("DataValidator initialized with %d rules", len(self._rules))

    # ── Built-in rules ─────────────────────────────

    def _register_builtin_rules(self) -> None:
        """Register all built-in validation rules."""

        # Price rules
        self._rules["price_non_negative"] = ValidationRule(
            rule_id="price_non_negative",
            rule_type=ValidationRuleType.PRICE,
            description="Price must be non-negative",
            severity="error",
        )
        self._rules["price_reasonable"] = ValidationRule(
            rule_id="price_reasonable",
            rule_type=ValidationRuleType.PRICE,
            description="Price should be within reasonable range (0.000001 - 1e9)",
            severity="warning",
        )
        self._rules["price_stale"] = ValidationRule(
            rule_id="price_stale",
            rule_type=ValidationRuleType.PRICE,
            description="Price timestamp should not be too stale",
            severity="warning",
            params={"max_stale_seconds": 300},
        )

        # Volume rules
        self._rules["volume_non_negative"] = ValidationRule(
            rule_id="volume_non_negative",
            rule_type=ValidationRuleType.VOLUME,
            description="Volume must be non-negative",
            severity="error",
        )

        # Spread rules
        self._rules["spread_non_negative"] = ValidationRule(
            rule_id="spread_non_negative",
            rule_type=ValidationRuleType.SPREAD,
            description="Bid must not exceed Ask",
            severity="error",
        )

        # Timestamp rules
        self._rules["timestamp_not_future"] = ValidationRule(
            rule_id="timestamp_not_future",
            rule_type=ValidationRuleType.TIMESTAMP,
            description="Timestamp must not be in the future",
            severity="error",
            params={"tolerance_ns": 60_000_000_000},  # 60s
        )
        self._rules["timestamp_not_zero"] = ValidationRule(
            rule_id="timestamp_not_zero",
            rule_type=ValidationRuleType.TIMESTAMP,
            description="Timestamp must not be zero",
            severity="error",
        )

        # Symbol rules
        self._rules["symbol_not_empty"] = ValidationRule(
            rule_id="symbol_not_empty",
            rule_type=ValidationRuleType.SYMBOL,
            description="Symbol/Instrument ID must not be empty",
            severity="error",
        )

    # ── Validation ─────────────────────────────────

    async def validate(self, data: CanonicalMarketData) -> DataValidationReport:
        """Run all enabled validation rules against canonical market data."""
        start_ns = self._now_ns()
        report = DataValidationReport(
            instrument_id=data.instrument_id,
            event_type=data.event_type.value,
        )

        # Run each rule
        for rule_id, rule in self._rules.items():
            if not rule.is_enabled:
                report.rule_results[rule_id] = True
                continue

            passed, error = self._execute_rule(rule, data)
            report.rule_results[rule_id] = passed

            if not passed and error:
                if error.severity == "error":
                    report.errors.append(error)
                else:
                    report.warnings.append(error)

        report.is_valid = len(report.errors) == 0
        report.validated_at = datetime.now(timezone.utc)
        report.duration_us = (self._now_ns() - start_ns) / 1000.0

        self._stats["total_validated"] += 1
        self._stats["total_errors"] += len(report.errors)
        self._stats["total_warnings"] += len(report.warnings)

        return report

    async def validate_batch(
        self, data_batch: list[CanonicalMarketData]
    ) -> list[DataValidationReport]:
        """Validate a batch of market data records."""
        return [await self.validate(data) for data in data_batch]

    # ── Rule execution ─────────────────────────────

    def _execute_rule(
        self, rule: ValidationRule, data: CanonicalMarketData
    ) -> tuple[bool, Optional[DataValidationError]]:
        """Execute a single validation rule."""

        make_err = lambda msg, field="", value=None, threshold=None: DataValidationError(
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            message=msg,
            severity=rule.severity,
            field=field,
            value=value,
            threshold=threshold,
            timestamp_ns=data.event_timestamp_ns,
        )

        if rule.rule_id == "price_non_negative":
            last = getattr(data, "last", None) or Decimal("0")
            if last < 0:
                return False, make_err(f"Negative price: {last}", "last", str(last))

        elif rule.rule_id == "price_reasonable":
            last = getattr(data, "last", None) or Decimal("0")
            if last > 0 and (last < Decimal("0.000001") or last > Decimal("1000000000")):
                return False, make_err(f"Unreasonable price: {last}", "last", str(last))

        elif rule.rule_id == "volume_non_negative":
            volume = getattr(data, "volume", None) or Decimal("0")
            if volume < 0:
                return False, make_err(f"Negative volume: {volume}", "volume", str(volume))

        elif rule.rule_id == "spread_non_negative":
            bid = getattr(data, "bid", None) or Decimal("0")
            ask = getattr(data, "ask", None) or Decimal("0")
            if bid > 0 and ask > 0 and bid > ask:
                return False, make_err(f"Bid ({bid}) > Ask ({ask})", "spread", str(bid), str(ask))

        elif rule.rule_id == "timestamp_not_future":
            tolerance = rule.params.get("tolerance_ns", 60_000_000_000)
            now_ns = self._now_ns()
            if data.event_timestamp_ns > now_ns + tolerance:
                return False, make_err("Timestamp in future", "event_timestamp_ns",
                                       str(data.event_timestamp_ns))

        elif rule.rule_id == "timestamp_not_zero":
            if data.event_timestamp_ns == 0:
                return False, make_err("Timestamp is zero", "event_timestamp_ns")

        elif rule.rule_id == "symbol_not_empty":
            if not data.instrument_id and not getattr(data, "canonical_symbol", ""):
                return False, make_err("Empty symbol/instrument ID", "instrument_id")

        elif rule.rule_id == "price_stale":
            max_stale = rule.params.get("max_stale_seconds", 300)
            now_ns = self._now_ns()
            stale_ns = max_stale * 1_000_000_000
            if data.event_timestamp_ns > 0 and (now_ns - data.event_timestamp_ns) > stale_ns:
                return False, make_err(f"Price stale: {(now_ns - data.event_timestamp_ns) / 1e9:.0f}s old",
                                       "event_timestamp_ns")

        return True, None

    # ── Rule management ────────────────────────────

    async def add_rule(self, rule: ValidationRule) -> None:
        """Register a custom validation rule."""
        self._rules[rule.rule_id] = rule
        logger.info("Added validation rule: %s", rule.rule_id)

    async def enable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].is_enabled = True

    async def disable_rule(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].is_enabled = False

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)


# Type alias for __init__.py compatibility
DataValidationRule = ValidationRule
