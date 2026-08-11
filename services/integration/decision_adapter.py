"""
Decision Adapter — bridges governance decisions into the integration control flow.

Commit 21 Part 1.1: translates DecisionResult from the governance layer
into structured data for the integration gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class DecisionAdapter:
    """Bridges governance DecisionResult into the integration layer."""

    @staticmethod
    def adapt_decision_result(decision_result: Any) -> Dict[str, Any]:
        """Extract integration-relevant fields from a DecisionResult."""
        return {
            "decision_id": getattr(decision_result, "decision_id", None),
            "request_id": getattr(decision_result, "request_id", ""),
            "outcome": getattr(getattr(decision_result, "outcome", None), "name", "UNKNOWN"),
            "is_allowed": getattr(decision_result, "is_allowed", False),
            "allowed_amount": getattr(decision_result, "allowed_amount", None),
            "reason": getattr(decision_result, "reason", ""),
        }

    @staticmethod
    def adapt_decision_request(decision_request: Any) -> Dict[str, Any]:
        """Extract integration-relevant fields from a DecisionRequest."""
        return {
            "request_id": getattr(decision_request, "request_id", ""),
            "actor": getattr(decision_request, "actor", "SYSTEM"),
            "decision_type": getattr(getattr(decision_request, "decision_type", None), "name", ""),
            "strategy_id": getattr(decision_request, "strategy_id", None),
            "portfolio_id": getattr(decision_request, "portfolio_id", None),
            "asset_id": getattr(decision_request, "asset_id", None),
            "requested_amount": getattr(decision_request, "requested_amount", None),
            "requested_quantity": getattr(decision_request, "requested_quantity", None),
            "requested_leverage": getattr(decision_request, "requested_leverage", None),
            "direction": getattr(decision_request, "direction", ""),
            "is_risk_increasing": getattr(decision_request, "is_risk_increasing", True),
            "reason": getattr(decision_request, "reason", ""),
        }

    @staticmethod
    def is_decision_allowed(decision_result: Any) -> bool:
        """Check if a DecisionResult allows the action."""
        return getattr(decision_result, "is_allowed", False)

    @staticmethod
    def get_rejection_reason(decision_result: Any) -> str:
        """Get the rejection reason from a DecisionResult."""
        return getattr(decision_result, "reason", "Unknown rejection")
