"""
Return on Capital (ROC) — Return Metrics for Capital Allocation

Computes various return-on-capital metrics:
- ROC (Return on Capital): Return / Capital
- RORAC (Return on Risk-Adjusted Capital): Return / Risk Capital
- RAROC (Risk-Adjusted Return on Capital): Risk-Adjusted Return / Capital
- RARORAC (Risk-Adjusted Return on Risk-Adjusted Capital)
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ROCMetrics:
    strategy_id: str
    capital: float = 0.0
    risk_capital: float = 0.0
    expected_return: float = 0.0
    risk_adjusted_return: float = 0.0
    roc: float = 0.0       # Return / Capital
    rorac: float = 0.0     # Return / Risk Capital
    raroc: float = 0.0     # Risk-Adjusted Return / Capital
    rarorac: float = 0.0   # Risk-Adjusted Return / Risk Capital
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ReturnOnCapital:
    """
    Computes and tracks ROC family metrics.

    ROC      = Expected Return / Capital Allocated
    RORAC    = Expected Return / Risk Capital (Economic Capital)
    RAROC    = Risk-Adjusted Expected Return / Capital Allocated
    RARORAC  = Risk-Adjusted Expected Return / Risk Capital
    """

    def __init__(
        self,
        roc_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.roc_id = roc_id or f"roc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._metrics: Dict[str, ROCMetrics] = {}

    def compute(
        self,
        strategy_id: str,
        capital: float,
        expected_return: float,
        risk_capital: float = 0.0,
        risk_adjusted_return: Optional[float] = None,
    ) -> ROCMetrics:
        risk_adjusted_return = risk_adjusted_return or expected_return
        rc = risk_capital if risk_capital > 0 else capital

        metrics = ROCMetrics(
            strategy_id=strategy_id,
            capital=capital,
            risk_capital=rc,
            expected_return=expected_return,
            risk_adjusted_return=risk_adjusted_return,
            roc=expected_return / capital if capital > 0 else 0.0,
            rorac=expected_return / rc if rc > 0 else 0.0,
            raroc=risk_adjusted_return / capital if capital > 0 else 0.0,
            rarorac=risk_adjusted_return / rc if rc > 0 else 0.0,
        )
        self._metrics[strategy_id] = metrics
        return metrics

    def get(self, strategy_id: str) -> Optional[ROCMetrics]:
        return self._metrics.get(strategy_id)

    def rank_by_roc(self) -> Dict[str, float]:
        return {
            sid: m.roc
            for sid, m in sorted(self._metrics.items(), key=lambda x: -x[1].roc)
        }

    def rank_by_raroc(self) -> Dict[str, float]:
        return {
            sid: m.raroc
            for sid, m in sorted(self._metrics.items(), key=lambda x: -x[1].raroc)
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "roc_id": self.roc_id,
            "strategy_count": len(self._metrics),
            "average_roc": sum(m.roc for m in self._metrics.values()) / max(1, len(self._metrics)),
            "strategies": self.rank_by_roc(),
        }
