"""
Marginal Capital Efficiency (MCE) — "Next Dollar" Analysis

The critical metric for dynamic capital allocation:

    MCE(strategy) = ΔExpected Return / ΔCapital

Answers: "If I add one more dollar to this strategy, what do I get back?"

Strategies with higher MCE should receive capital from strategies
with lower MCE. This drives the reallocation engine.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCERecord:
    strategy_id: str
    mce: float = 0.0
    current_capital: float = 0.0
    current_return: float = 0.0
    marginal_return_per_unit: float = 0.0
    step_size: float = 0.0
    diminishing: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MarginalCapitalEfficiency:
    """
    Computes marginal capital efficiency for reallocation decisions.

    MCE guides the "where should the next dollar go" question:
    - Higher MCE → allocate more capital
    - Lower/Negative MCE → reduce or deallocate
    - Diminishing MCE → approaching capacity limit

    The reallocation engine uses MCE to move capital from
    low-MCE strategies to high-MCE strategies.
    """

    def __init__(
        self,
        mce_id: Optional[str] = None,
        capacity_manager=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.mce_id = mce_id or f"mce-{uuid.uuid4().hex[:12]}"
        self._capacity_manager = capacity_manager
        self.config = config or {}
        self._default_step_size = self.config.get("step_size", 1_000_000)
        self._records: Dict[str, MCERecord] = {}
        self._history: Dict[str, List[MCERecord]] = {}

    def estimate(
        self,
        strategy_id: str,
        current_capital: float,
        current_return: float,
        step_size: Optional[float] = None,
    ) -> MCERecord:
        """
        Estimate MCE for a strategy at current capital level.

        Uses capacity profile if available for non-linear estimation.
        """
        step = step_size or self._default_step_size
        diminishing = False

        if self._capacity_manager:
            marginal_return = self._capacity_manager.get_marginal_return(strategy_id, step)
            mce = marginal_return / step if step > 0 else 0.0
            profile = self._capacity_manager.get(strategy_id)
            if profile and current_capital > profile.optimal_capital:
                diminishing = True
        else:
            # Linear approximation
            unit_return = current_return / current_capital if current_capital > 0 else 0.0
            mce = unit_return
            marginal_return_per_unit = unit_return

        record = MCERecord(
            strategy_id=strategy_id,
            mce=mce,
            current_capital=current_capital,
            current_return=current_return,
            marginal_return_per_unit=marginal_return_per_unit if 'marginal_return_per_unit' in dir() else 0.0,
            step_size=step,
            diminishing=diminishing,
        )
        self._records[strategy_id] = record
        self._history.setdefault(strategy_id, []).append(record)
        return record

    def get(self, strategy_id: str) -> Optional[MCERecord]:
        return self._records.get(strategy_id)

    def get_all_mce(self) -> Dict[str, float]:
        return {sid: r.mce for sid, r in self._records.items()}

    def rank(self) -> List[Tuple[str, float]]:
        """Rank strategies by MCE (descending)."""
        return sorted(
            [(sid, r.mce) for sid, r in self._records.items()],
            key=lambda x: -x[1],
        )

    def identify_capital_flows(self) -> List[Dict[str, Any]]:
        """
        Identify capital reallocation opportunities.

        Capital should flow from low-MCE to high-MCE strategies.
        """
        ranked = self.rank()
        if len(ranked) < 2:
            return []

        flows = []
        best = ranked[0]
        worst = ranked[-1]

        if best[1] > worst[1] * 1.5:  # At least 50% better
            flows.append({
                "from": worst[0],
                "from_mce": worst[1],
                "to": best[0],
                "to_mce": best[1],
                "efficiency_gap": best[1] - worst[1],
            })

        return flows

    def get_summary(self) -> Dict[str, Any]:
        return {
            "mce_id": self.mce_id,
            "ranking": self.rank(),
            "flows": self.identify_capital_flows(),
        }
