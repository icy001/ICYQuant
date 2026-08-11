"""Allocation Request — formal allocation change request.

Represents a request to change capital allocation for a strategy.
Flows through: requester → controller → optimizer → guard → execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RequestType(str, Enum):
    """Type of allocation request."""
    NEW_ALLOCATION = "NEW_ALLOCATION"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    FULL_REDEMPTION = "FULL_REDEMPTION"
    REBALANCE = "REBALANCE"
    ROTATION = "ROTATION"


class RequestPriority(str, Enum):
    """Priority of the allocation request."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class RequestStatus(str, Enum):
    """Lifecycle status of the request."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    RESIZED = "RESIZED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class RequestConstraints:
    """Constraints attached to an allocation request."""
    max_capital: Optional[float] = None
    min_capital: Optional[float] = None
    max_leverage: float = 1.0
    max_weight: float = 1.0
    min_weight: float = 0.0
    allowed_assets: List[str] = field(default_factory=list)
    restricted_assets: List[str] = field(default_factory=list)
    max_single_asset_weight: float = 1.0
    max_sector_weight: float = 1.0
    max_factor_exposure: float = 1.0


@dataclass
class AllocationRequest:
    """Formal request to change capital allocation for a strategy."""

    strategy_id: str
    request_type: RequestType = RequestType.NEW_ALLOCATION
    priority: RequestPriority = RequestPriority.NORMAL
    status: RequestStatus = RequestStatus.DRAFT

    # Target
    target_capital: float = 0.0
    target_weight: float = 0.0
    capital_delta: float = 0.0

    # Context
    current_capital: float = 0.0
    current_weight: float = 0.0
    rationale: str = ""
    expected_alpha: float = 0.0
    expected_risk: float = 0.0
    expected_cost: float = 0.0

    # Constraints
    constraints: RequestConstraints = field(default_factory=RequestConstraints)

    # Meta
    request_id: str = ""
    parent_request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiry: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.request_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.request_id = f"req-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"
        self.capital_delta = self.target_capital - self.current_capital

    @property
    def is_increase(self) -> bool:
        return self.capital_delta > 0

    @property
    def is_decrease(self) -> bool:
        return self.capital_delta < 0

    @property
    def is_expired(self) -> bool:
        if self.expiry is None:
            return False
        return datetime.utcnow() > self.expiry

    def update_status(self, new_status: RequestStatus, reason: str = "") -> None:
        """Update request status with history tracking."""
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "from_status": self.status.value,
            "to_status": new_status.value,
            "reason": reason,
        })
        self.status = new_status

    def resize(self, new_delta: float, reason: str = "") -> None:
        """Resize the capital delta."""
        old_delta = self.capital_delta
        self.capital_delta = new_delta
        self.target_capital = self.current_capital + new_delta
        self.update_status(
            RequestStatus.RESIZED,
            f"Resized from {old_delta:,.0f} to {new_delta:,.0f}: {reason}"
        )

    def validate(self) -> List[str]:
        """Validate the request against its own constraints."""
        errors = []
        c = self.constraints

        if c.max_capital is not None and self.target_capital > c.max_capital:
            errors.append(f"Target capital {self.target_capital:,.0f} exceeds max {c.max_capital:,.0f}")

        if c.min_capital is not None and self.target_capital < c.min_capital:
            errors.append(f"Target capital {self.target_capital:,.0f} below min {c.min_capital:,.0f}")

        if self.target_weight > c.max_weight:
            errors.append(f"Target weight {self.target_weight:.4f} exceeds max {c.max_weight:.4f}")

        if self.target_weight < c.min_weight:
            errors.append(f"Target weight {self.target_weight:.4f} below min {c.min_weight:.4f}")

        return errors

    def summarize(self) -> str:
        """Generate a human-readable summary."""
        return (
            f"AllocationRequest[{self.request_id}] {self.request_type.value} "
            f"{self.strategy_id}: {self.current_capital:,.0f}→{self.target_capital:,.0f} "
            f"({self.capital_delta:+,.0f}) [{self.status.value}]"
        )
