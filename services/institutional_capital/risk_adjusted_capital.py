"""
Risk-Adjusted Capital — Risk-Weighted Capital Allocation

Computes Risk-Adjusted Capital (RAC) for strategies, which is the
capital weighted by risk contribution. Used in RORAC/RAROC calculations.

    Risk-Adjusted Capital = Capital × Risk Weight
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RiskAdjustedCapitalRecord:
    strategy_id: str
    nominal_capital: float = 0.0
    risk_weight: float = 1.0
    risk_adjusted_capital: float = 0.0
    risk_contribution: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskAdjustedCapital:
    """
    Computes risk-adjusted capital for each strategy.

    RAC = Nominal Capital × Risk Weight
    where risk weight is derived from volatility, VaR, or other risk measures.
    """

    def __init__(
        self,
        rac_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.rac_id = rac_id or f"rac-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._records: Dict[str, RiskAdjustedCapitalRecord] = {}
        self._base_risk_weight = self.config.get("base_risk_weight", 1.0)

    def compute(
        self,
        strategy_id: str,
        nominal_capital: float,
        volatility: float = 0.0,
        var_95: float = 0.0,
        risk_contribution: float = 0.0,
    ) -> RiskAdjustedCapitalRecord:
        """
        Compute risk-adjusted capital.

        Risk weight combines:
        - Volatility-based weight
        - VaR-based weight
        - Fallback to base weight
        """
        risk_weight = self._base_risk_weight
        if volatility > 0:
            risk_weight = max(risk_weight, volatility / 0.15)  # Normalize to 15% vol
        if var_95 > 0 and nominal_capital > 0:
            var_weight = abs(var_95) / nominal_capital
            risk_weight = max(risk_weight, var_weight)

        rac = nominal_capital * risk_weight

        record = RiskAdjustedCapitalRecord(
            strategy_id=strategy_id,
            nominal_capital=nominal_capital,
            risk_weight=risk_weight,
            risk_adjusted_capital=rac,
            risk_contribution=risk_contribution,
        )
        self._records[strategy_id] = record
        return record

    def get(self, strategy_id: str) -> Optional[RiskAdjustedCapitalRecord]:
        return self._records.get(strategy_id)

    def get_all_rac(self) -> Dict[str, float]:
        return {sid: r.risk_adjusted_capital for sid, r in self._records.items()}

    def get_total_rac(self) -> float:
        return sum(r.risk_adjusted_capital for r in self._records.values())

    def get_summary(self) -> Dict[str, Any]:
        return {
            "rac_id": self.rac_id,
            "total_rac": self.get_total_rac(),
            "strategies": {
                sid: {
                    "nominal": r.nominal_capital,
                    "weight": r.risk_weight,
                    "rac": r.risk_adjusted_capital,
                }
                for sid, r in self._records.items()
            },
        }
