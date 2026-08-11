"""
Aggregate Factor Risk — Portfolio-Level Factor Risk Management

Detects when different strategies concentrate on the same factor,
creating hidden portfolio-level factor risk.

    Strategy A → Growth +0.6
    Strategy B → Growth +0.4
    Strategy C → Growth +0.7
    ──────────────────────────
    Portfolio Growth = +1.7  (Single factor concentration!)

This is NOT 3 independent strategies, but 1 large factor bet.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FactorRiskAggregate:
    factor_name: str
    total_exposure: float
    contributing_strategies: Dict[str, float]
    concentration_warning: bool = False
    severity: str = "OK"


class AggregateFactorRisk:
    """
    Aggregates factor exposures across all strategies to detect
    hidden factor concentrations at the portfolio level.
    """

    def __init__(
        self,
        afr_id: Optional[str] = None,
        strategy_exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.afr_id = afr_id or f"afr-{uuid.uuid4().hex[:12]}"
        self._strategy_exposure = strategy_exposure
        self.config = config or {}
        self._concentration_threshold = self.config.get("factor_concentration_threshold", 1.0)
        self._aggregates: Dict[str, FactorRiskAggregate] = {}

    def aggregate(self) -> Dict[str, FactorRiskAggregate]:
        """Aggregate factor exposures across all strategies."""
        self._aggregates.clear()

        if not self._strategy_exposure:
            return self._aggregates

        profiles = self._strategy_exposure.get_all_profiles()
        factor_map: Dict[str, Dict[str, float]] = {}

        for sid, profile in profiles.items():
            for fname, fexp in profile.factor_exposures.items():
                factor_map.setdefault(fname, {})[sid] = fexp.exposure

        for fname, exposures in factor_map.items():
            total = sum(exposures.values())
            warning = abs(total) > self._concentration_threshold
            severity = "HIGH" if abs(total) > self._concentration_threshold * 1.5 else (
                "MEDIUM" if warning else "OK"
            )

            self._aggregates[fname] = FactorRiskAggregate(
                factor_name=fname,
                total_exposure=total,
                contributing_strategies=exposures,
                concentration_warning=warning,
                severity=severity,
            )

        return self._aggregates

    def get_warnings(self) -> List[FactorRiskAggregate]:
        return [a for a in self._aggregates.values() if a.concentration_warning]

    def get_factor_exposure(self, factor_name: str) -> Optional[FactorRiskAggregate]:
        return self._aggregates.get(factor_name)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "afr_id": self.afr_id,
            "factors": len(self._aggregates),
            "warnings": len(self.get_warnings()),
            "concentrations": {
                f: {"total": a.total_exposure, "severity": a.severity}
                for f, a in self._aggregates.items() if a.concentration_warning
            },
        }
