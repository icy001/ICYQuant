"""AdmissionValidator — structural and business validation of admission requests.

Validates both basic field integrity (non-empty, positive values) and
business rules (e.g., LIMIT order must have limit_price).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .admission_request import AdmissionRequest
from .order_intent import OrderIntent, OrderType, Side


@dataclass
class ValidationError:
    """A single validation error."""
    field: str = ""
    code: str = ""
    message: str = ""


@dataclass
class ValidationReport:
    """Aggregated validation report."""
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, code: str, message: str) -> None:
        self.errors.append(ValidationError(field=field, code=code, message=message))
        self.valid = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [{"field": e.field, "code": e.code, "message": e.message}
                        for e in self.errors],
        }


@dataclass
class AdmissionValidator:
    """Validates admission requests for structural and business correctness."""

    def validate(self, request: AdmissionRequest) -> ValidationReport:
        """Run all validation checks on an admission request."""
        report = ValidationReport()

        if request.intent is None:
            report.add_error("intent", "MISSING_INTENT", "OrderIntent is required")
            return report

        intent = request.intent

        self._validate_identity(intent, report)
        self._validate_fields(intent, report)
        self._validate_business_rules(intent, report)

        return report

    def _validate_identity(self, intent: OrderIntent, report: ValidationReport) -> None:
        """Validate identity/context fields."""
        if not intent.flow_id:
            report.add_error("flow_id", "MISSING_FLOW_ID",
                             "flow_id is required")
        if not intent.decision_id:
            report.add_error("decision_id", "MISSING_DECISION_ID",
                             "decision_id is required")
        if not intent.strategy_id:
            report.add_error("strategy_id", "MISSING_STRATEGY_ID",
                             "strategy_id is required")
        if not intent.account_id:
            report.add_error("account_id", "MISSING_ACCOUNT_ID",
                             "account_id is required")

    def _validate_fields(self, intent: OrderIntent, report: ValidationReport) -> None:
        """Validate core order fields."""
        if not intent.symbol:
            report.add_error("symbol", "MISSING_SYMBOL",
                             "symbol is required")

        if intent.quantity <= 0:
            report.add_error("quantity", "INVALID_QUANTITY",
                             f"quantity must be positive, got {intent.quantity}")

        if intent.side not in (Side.BUY, Side.SELL):
            report.add_error("side", "INVALID_SIDE",
                             f"side must be BUY or SELL, got {intent.side.name}")

        if intent.order_type not in (
            OrderType.MARKET, OrderType.LIMIT,
            OrderType.STOP, OrderType.STOP_LIMIT,
        ):
            report.add_error("order_type", "INVALID_ORDER_TYPE",
                             f"invalid order type: {intent.order_type.name}")

    def _validate_business_rules(self, intent: OrderIntent, report: ValidationReport) -> None:
        """Validate business rules (cross-field constraints)."""
        # LIMIT and STOP_LIMIT orders must have limit_price
        if intent.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            if intent.limit_price is None or intent.limit_price <= 0:
                report.add_error(
                    "limit_price", "MISSING_LIMIT_PRICE",
                    f"LIMIT order requires valid limit_price, got {intent.limit_price}"
                )

        # STOP and STOP_LIMIT orders must have stop_price
        if intent.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            if intent.stop_price is None or intent.stop_price <= 0:
                report.add_error(
                    "stop_price", "MISSING_STOP_PRICE",
                    f"STOP order requires valid stop_price, got {intent.stop_price}"
                )

        # Notional must be positive if both quantity and price are set
        if intent.limit_price and intent.limit_price > 0:
            notional = intent.quantity * intent.limit_price
            if notional <= 0:
                report.add_error(
                    "notional", "INVALID_NOTIONAL",
                    f"notional must be positive, got {notional} "
                    f"(quantity={intent.quantity}, price={intent.limit_price})"
                )

    def __repr__(self) -> str:
        return "AdmissionValidator()"
