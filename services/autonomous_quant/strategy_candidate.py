"""Strategy Candidate — Tracked strategy candidate object.

Lifecycle: DRAFT → BACKTESTING → VALIDATED → CANDIDATE → REJECTED/PROMOTED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class StrategyCandidate:
    strategy_id: str
    alpha_id: str
    entry_rules: List[str] = field(default_factory=list)
    exit_rules: List[str] = field(default_factory=list)
    position_sizing: str = "equal_weight"
    risk_rules: List[str] = field(default_factory=list)
    universe: List[str] = field(default_factory=list)
    execution_constraints: List[str] = field(default_factory=list)
    status: str = "draft"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    backtest_id: Optional[str] = None
    performance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "alpha_id": self.alpha_id,
            "entry_rules": self.entry_rules,
            "exit_rules": self.exit_rules,
            "position_sizing": self.position_sizing,
            "risk_rules": self.risk_rules,
            "universe": self.universe,
            "execution_constraints": self.execution_constraints,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "backtest_id": self.backtest_id,
            "performance": self.performance,
        }
