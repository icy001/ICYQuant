"""RiskAction — base risk action interface and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class RiskActionCategory(Enum):
    """Categories of risk actions."""

    NONE = auto()
    FREEZE = auto()
    REDUCE = auto()
    DELEVERAGE = auto()
    REALLOCATE = auto()
    HEDGE = auto()
    EXIT = auto()
    EMERGENCY = auto()


class RiskActionPriority(Enum):
    """Priority levels for risk actions."""

    LOW = 100
    MEDIUM = 50
    HIGH = 25
    CRITICAL = 10
    EMERGENCY = 1


@dataclass
class RiskActionRequest:
    """A request for a risk action."""

    action_id: str
    category: RiskActionCategory = RiskActionCategory.NONE
    priority: RiskActionPriority = RiskActionPriority.MEDIUM
    entity_id: str = ""
    target_reduction_pct: float = 0.0
    target_value: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class RiskActionResult:
    """Result of executing a risk action."""

    action_id: str
    success: bool = False
    actual_reduction: float = 0.0
    new_survival_score: float = 0.0
    new_risk_budget_used: float = 0.0
    message: str = ""


class RiskActionRegistry:
    """Registry for risk action handlers.

    Usage::

        registry = RiskActionRegistry()
        registry.register(RiskActionCategory.REDUCE, my_reduce_handler)
        result = registry.execute(reduce_request)
    """

    def __init__(self):
        self._handlers: Dict[RiskActionCategory, Any] = {}

    def register(self, category: RiskActionCategory, handler: Any) -> None:
        self._handlers[category] = handler

    def execute(self, request: RiskActionRequest) -> RiskActionResult:
        """Execute a risk action request."""
        handler = self._handlers.get(request.category)
        if handler is None:
            return RiskActionResult(
                action_id=request.action_id,
                success=False,
                message=f"No handler for {request.category.name}",
            )

        try:
            return handler(request)
        except Exception as e:
            return RiskActionResult(
                action_id=request.action_id,
                success=False,
                message=str(e),
            )
