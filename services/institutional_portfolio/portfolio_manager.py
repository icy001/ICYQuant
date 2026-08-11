"""
Portfolio Manager — Operational Command Layer

Translates orchestration decisions into executable actions:
- Execute netting operations
- Apply portfolio construction targets
- Trigger rebalances
- Manage strategy lifecycle (activate, quarantine, replace)
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ManagerAction(str, Enum):
    NET_SIGNALS = "NET_SIGNALS"
    NET_POSITIONS = "NET_POSITIONS"
    BUILD_PORTFOLIO = "BUILD_PORTFOLIO"
    REBALANCE = "REBALANCE"
    QUARANTINE_STRATEGY = "QUARANTINE_STRATEGY"
    REPLACE_STRATEGY = "REPLACE_STRATEGY"
    ACTIVATE_STRATEGY = "ACTIVATE_STRATEGY"
    DEACTIVATE_STRATEGY = "DEACTIVATE_STRATEGY"


@dataclass
class ManagerOperation:
    op_id: str
    action: ManagerAction
    status: str = "PENDING"
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class PortfolioManager:
    """
    Executes portfolio orchestration actions.

    Bridges orchestration decisions with operational execution.
    Handles strategy lifecycle and portfolio construction.
    """

    def __init__(
        self,
        manager_id: Optional[str] = None,
        portfolio=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.manager_id = manager_id or f"pm-{uuid.uuid4().hex[:12]}"
        self._portfolio = portfolio
        self.config = config or {}
        self._operations: List[ManagerOperation] = []
        self._history: List[ManagerOperation] = []

    def execute(self, action: ManagerAction, params: Optional[Dict] = None) -> ManagerOperation:
        op = ManagerOperation(
            op_id=f"mo-{uuid.uuid4().hex[:8]}",
            action=action,
            params=params or {},
        )

        try:
            handlers = {
                ManagerAction.NET_SIGNALS: self._net_signals,
                ManagerAction.NET_POSITIONS: self._net_positions,
                ManagerAction.BUILD_PORTFOLIO: self._build_portfolio,
                ManagerAction.REBALANCE: self._rebalance,
                ManagerAction.QUARANTINE_STRATEGY: self._quarantine,
                ManagerAction.REPLACE_STRATEGY: self._replace,
            }
            handler = handlers.get(action)
            if handler:
                handler(op)
            op.status = "COMPLETED"
        except Exception as e:
            op.status = "FAILED"
            op.error = str(e)
            logger.error(f"Operation {op.op_id} failed: {e}")

        op.completed_at = datetime.utcnow()
        self._history.append(op)
        return op

    def _net_signals(self, op: ManagerOperation) -> None:
        if self._portfolio and self._portfolio._signal_netting:
            self._portfolio._signal_netting.net()

    def _net_positions(self, op: ManagerOperation) -> None:
        if self._portfolio and self._portfolio._position_netting:
            self._portfolio._position_netting.net()

    def _build_portfolio(self, op: ManagerOperation) -> None:
        if self._portfolio and self._portfolio._portfolio_builder:
            self._portfolio._portfolio_builder.build()

    def _rebalance(self, op: ManagerOperation) -> None:
        if self._portfolio and self._portfolio._rebalance_engine:
            self._portfolio._rebalance_engine.execute()

    def _quarantine(self, op: ManagerOperation) -> None:
        sid = op.params.get("strategy_id")
        if self._portfolio and sid:
            self._portfolio.quarantine_strategy(sid)

    def _replace(self, op: ManagerOperation) -> None:
        old = op.params.get("old_id")
        new = op.params.get("new_id")
        if self._portfolio and old and new:
            self._portfolio.replace_strategy(old, new)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "operations": len(self._history),
            "failed": sum(1 for o in self._history if o.status == "FAILED"),
        }
