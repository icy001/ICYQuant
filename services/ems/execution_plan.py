"""Execution Plan — Execution plan definition and management.

An execution plan defines how a parent order will be executed, including
the algorithm strategy, timing, and constraints.

Structure::

    ExecutionContext → ExecutionPlan → Algorithm → Child Orders

Usage::

    plan = ExecutionPlan(context=context)
    plan.validate()
    plan.add_constraint("max_slippage", 5.0)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.execution_context import ExecutionContext
from services.ems.execution_state import ExecutionStatus


@dataclass
class ExecutionConstraint:
    """An execution constraint or limit.

    Attributes:
        name: Constraint name (e.g., max_slippage, min_fill_rate)
        value: Constraint value
        is_hard: Whether violation should halt execution
    """

    name: str
    value: Any
    is_hard: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "is_hard": self.is_hard,
        }


@dataclass
class ExecutionPlan:
    """Execution plan for a parent order.

    Defines the complete execution strategy including algorithm choice,
    timing, constraints, and slicing parameters.

    Attributes:
        plan_id: Unique plan identifier
        context: Execution context with order and strategy
        status: Current plan status
        constraints: List of execution constraints
        tags: Arbitrary tags for categorization
        created_at: Plan creation time
        updated_at: Last update time
    """

    context: ExecutionContext
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ExecutionStatus = ExecutionStatus.PENDING
    constraints: list[ExecutionConstraint] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def parent_order_id(self) -> str:
        """Parent order ID from context."""
        return self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""

    @property
    def strategy(self) -> str:
        """Strategy name from context."""
        return self.context.strategy

    @property
    def total_quantity(self) -> float:
        """Total quantity from context."""
        return self.context.total_quantity

    def add_constraint(self, name: str, value: Any, is_hard: bool = True) -> None:
        """Add an execution constraint.

        Args:
            name: Constraint name
            value: Constraint value
            is_hard: Whether violation halts execution
        """
        # Remove existing constraint with same name
        self.constraints = [c for c in self.constraints if c.name != name]
        self.constraints.append(ExecutionConstraint(name=name, value=value, is_hard=is_hard))
        self.updated_at = datetime.now(timezone.utc)

    def get_constraint(self, name: str) -> Optional[ExecutionConstraint]:
        """Get a constraint by name."""
        for c in self.constraints:
            if c.name == name:
                return c
        return None

    def validate(self) -> list[str]:
        """Validate the execution plan.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = self.context.validate()
        if self.total_quantity <= 0:
            errors.append("Total quantity must be positive")
        if self.context.effective_duration <= 0:
            errors.append("Duration must be positive")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize plan to dictionary."""
        return {
            "plan_id": self.plan_id,
            "parent_order_id": self.parent_order_id,
            "strategy": self.strategy,
            "status": self.status.value,
            "total_quantity": self.total_quantity,
            "context": self.context.to_dict(),
            "constraints": [c.to_dict() for c in self.constraints],
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
