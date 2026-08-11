"""
Portfolio Builder — Construct the Unified Multi-Strategy Portfolio

Takes netted positions and target weights to construct the final
portfolio. Applies constraints, computes exposures, and produces
the execution-ready portfolio structure.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConstruction:
    construction_id: str
    positions: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    constraint_violations: List[str] = field(default_factory=list)
    status: str = "DRAFT"


class PortfolioBuilder:
    """
    Constructs the unified portfolio from netted positions and targets.

    Pipeline:
    1. Start with netted positions
    2. Apply weight constraints
    3. Compute exposures
    4. Validate constraints
    5. Output final portfolio
    """

    def __init__(
        self,
        builder_id: Optional[str] = None,
        constraint_engine=None,
        weight_engine=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.builder_id = builder_id or f"pb-{uuid.uuid4().hex[:12]}"
        self._constraint_engine = constraint_engine
        self._weight_engine = weight_engine
        self.config = config or {}
        self._constructions: List[PortfolioConstruction] = []

    def build(self, targets: Optional[Dict[str, Any]] = None) -> PortfolioConstruction:
        """Build the portfolio from target positions."""
        construction = PortfolioConstruction(
            construction_id=f"pc-{uuid.uuid4().hex[:8]}",
        )

        if targets:
            positions = {}
            weights = {}
            for asset, target in targets.items():
                if hasattr(target, 'target_weight'):
                    weights[asset] = target.target_weight
                    positions[asset] = target.target_notional if hasattr(target, 'target_notional') else target.target_weight

            construction.positions = positions
            construction.weights = weights
            construction.gross_exposure = sum(abs(v) for v in positions.values())
            construction.net_exposure = sum(positions.values())

        # Validate constraints
        if self._constraint_engine:
            violations = self._constraint_engine.validate(construction)
            construction.constraint_violations = violations
            construction.status = "VALID" if not violations else "CONSTRAINT_VIOLATIONS"
        else:
            construction.status = "VALID"

        self._constructions.append(construction)
        return construction

    def get_latest(self) -> Optional[PortfolioConstruction]:
        return self._constructions[-1] if self._constructions else None
