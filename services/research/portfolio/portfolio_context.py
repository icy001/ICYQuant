"""Portfolio Context — shared context for portfolio research operations.

Carries session, trace, universe, benchmark, constraints, and
risk parameters across the portfolio research pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class PortfolioContext:
    """Contextual data propagated through portfolio research.

    Carries:
    * Session/trace identifiers
    * Universe and benchmark configuration
    * Alpha pool and factor model references
    * Optimization and risk parameters
    * Constraint and execution settings
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    experiment_id: Optional[str] = None
    portfolio_id: Optional[str] = None

    # ── universe and data ──────────────────────────────────────────────────
    universe: List[str] = field(default_factory=list)
    benchmark: str = "CSI300"
    frequency: str = "daily"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # ── alpha and factors ──────────────────────────────────────────────────
    alpha_pool: List[str] = field(default_factory=list)
    factor_model_id: Optional[str] = None
    covariance_method: str = "shrinkage"

    # ── optimization ───────────────────────────────────────────────────────
    optimizer_type: str = "mean_variance"
    risk_aversion: float = 1.0
    target_return: Optional[float] = None
    max_turnover: float = 0.50
    rebalance_frequency: str = "monthly"

    # ── risk ───────────────────────────────────────────────────────────────
    var_confidence: float = 0.95
    var_method: str = "historical"
    tracking_error_target: float = 0.05
    max_leverage: float = 1.0
    max_position_size: float = 0.10
    max_sector_exposure: float = 0.30

    # ── constraints ────────────────────────────────────────────────────────
    min_weight: float = 0.0
    max_weight: float = 0.20
    long_only: bool = True
    fully_invested: bool = True
    sector_constraints: Dict[str, float] = field(default_factory=dict)

    # ── extras ─────────────────────────────────────────────────────────────
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "portfolio_id": self.portfolio_id,
            "universe": self.universe,
            "benchmark": self.benchmark,
            "frequency": self.frequency,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "alpha_pool": self.alpha_pool,
            "factor_model_id": self.factor_model_id,
            "covariance_method": self.covariance_method,
            "optimizer_type": self.optimizer_type,
            "risk_aversion": self.risk_aversion,
            "target_return": self.target_return,
            "max_turnover": self.max_turnover,
            "rebalance_frequency": self.rebalance_frequency,
            "var_confidence": self.var_confidence,
            "var_method": self.var_method,
            "tracking_error_target": self.tracking_error_target,
            "max_leverage": self.max_leverage,
            "max_position_size": self.max_position_size,
            "max_sector_exposure": self.max_sector_exposure,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "long_only": self.long_only,
            "fully_invested": self.fully_invested,
            "sector_constraints": self.sector_constraints,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
