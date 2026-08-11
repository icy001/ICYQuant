"""
Capital Efficiency — Multi-Strategy Efficiency Analytics

Computes and tracks capital efficiency metrics across all strategies:
- Return on Capital (ROC)
- Risk-Adjusted Capital Efficiency (RACE)
- Marginal Capital Efficiency (MCE)
- Capital Utilization
- Capacity Utilization

Core formula:
    Capital Efficiency = Expected Return / Capital Consumed
    Risk-Adjusted CE = Expected Return / Risk Capital
    Marginal CE = Incremental Return / Incremental Capital
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EfficiencyRecord:
    strategy_id: str
    capital_efficiency: float = 0.0
    risk_adjusted_efficiency: float = 0.0
    marginal_efficiency: float = 0.0
    capital_utilization: float = 0.0
    capacity_utilization: float = 0.0
    capital_allocated: float = 0.0
    expected_return: float = 0.0
    expected_risk: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CapitalEfficiency:
    """
    Computes and tracks capital efficiency metrics across strategies.

    Key metrics:
    - Capital Efficiency = Expected Return / Capital Allocated
    - Risk-Adjusted CE = Expected Return / (Risk-Adjusted Capital)
    - Marginal CE = ΔReturn / ΔCapital (incremental analysis)
    """

    def __init__(
        self,
        efficiency_id: Optional[str] = None,
        capital_pool=None,
        strategy_pool=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.efficiency_id = efficiency_id or f"ceff-{uuid.uuid4().hex[:12]}"
        self._capital_pool = capital_pool
        self._strategy_pool = strategy_pool
        self.config = config or {}
        self._records: Dict[str, EfficiencyRecord] = {}
        self._history: Dict[str, List[EfficiencyRecord]] = {}

    def compute(
        self,
        strategy_id: str,
        capital_allocated: float,
        expected_return: float,
        expected_risk: float = 0.0,
        capacity: Optional[float] = None,
    ) -> EfficiencyRecord:
        """Compute efficiency metrics for a strategy."""
        ce = expected_return / capital_allocated if capital_allocated > 0 else 0.0
        race = expected_return / expected_risk if expected_risk > 0 else ce
        mce = ce  # Default: use current CE as marginal

        util = capital_allocated / self._capital_pool.total_capital if self._capital_pool and self._capital_pool.total_capital > 0 else 0.0
        cap_util = capital_allocated / capacity if capacity and capacity > 0 else 0.0

        record = EfficiencyRecord(
            strategy_id=strategy_id,
            capital_efficiency=ce,
            risk_adjusted_efficiency=race,
            marginal_efficiency=mce,
            capital_utilization=util,
            capacity_utilization=cap_util,
            capital_allocated=capital_allocated,
            expected_return=expected_return,
            expected_risk=expected_risk,
        )
        self._records[strategy_id] = record
        self._history.setdefault(strategy_id, []).append(record)
        return record

    def update_marginal(
        self,
        strategy_id: str,
        additional_capital: float,
        additional_return: float,
    ) -> None:
        """Update marginal capital efficiency."""
        rec = self._records.get(strategy_id)
        if not rec:
            return
        rec.marginal_efficiency = additional_return / additional_capital if additional_capital > 0 else 0.0

    def get(self, strategy_id: str) -> Optional[EfficiencyRecord]:
        return self._records.get(strategy_id)

    def get_strategy_efficiencies(self) -> Dict[str, float]:
        return {sid: r.capital_efficiency for sid, r in self._records.items()}

    def get_risk_adjusted_efficiencies(self) -> Dict[str, float]:
        return {sid: r.risk_adjusted_efficiency for sid, r in self._records.items()}

    def get_marginal_efficiencies(self) -> Dict[str, float]:
        return {sid: r.marginal_efficiency for sid, r in self._records.items()}

    def rank_by_efficiency(self) -> List[str]:
        """Rank strategies by capital efficiency (descending)."""
        return sorted(
            self._records.keys(),
            key=lambda sid: self._records[sid].capital_efficiency,
            reverse=True,
        )

    def rank_by_marginal(self) -> List[str]:
        """Rank strategies by marginal capital efficiency (descending)."""
        return sorted(
            self._records.keys(),
            key=lambda sid: self._records[sid].marginal_efficiency,
            reverse=True,
        )

    def get_overall_efficiency(self) -> float:
        total_capital = sum(r.capital_allocated for r in self._records.values())
        total_return = sum(r.expected_return for r in self._records.values())
        return total_return / total_capital if total_capital > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "efficiency_id": self.efficiency_id,
            "overall_efficiency": self.get_overall_efficiency(),
            "strategies": {
                sid: {
                    "ce": r.capital_efficiency,
                    "race": r.risk_adjusted_efficiency,
                    "mce": r.marginal_efficiency,
                    "utilization": r.capital_utilization,
                }
                for sid, r in self._records.items()
            },
        }
