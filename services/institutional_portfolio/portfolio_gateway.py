"""
Portfolio Gateway — External Integration Interface

Exposes the multi-strategy portfolio as a unified interface for:
- Control Plane integration
- Execution Engine integration
- Capital Intelligence integration
- External monitoring & alerting
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PortfolioGateway:
    """
    Unified gateway for external systems to interact with the
    multi-strategy portfolio system.

    Provides:
    - Read-only portfolio state queries
    - Mutations with controller gating
    - Event streaming for external consumers
    """

    def __init__(
        self,
        gateway_id: Optional[str] = None,
        portfolio=None,
        controller=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.gateway_id = gateway_id or f"pg-{uuid.uuid4().hex[:12]}"
        self._portfolio = portfolio
        self._controller = controller
        self.config = config or {}
        self._subscribers: List[Any] = []

    # ─── Read ──────────────────────────────────────────────

    def get_portfolio_state(self) -> Dict[str, Any]:
        if self._portfolio:
            return self._portfolio.get_summary()
        return {"error": "No portfolio"}

    def get_positions(self) -> Dict[str, float]:
        if self._portfolio:
            return self._portfolio._get_positions()
        return {}

    def get_exposures(self) -> Dict[str, float]:
        if self._portfolio:
            return {
                "gross": self._portfolio.get_gross_exposure(),
                "net": self._portfolio.get_net_exposure(),
                "leverage": self._portfolio.get_leverage(),
            }
        return {}

    def get_risk(self) -> Dict[str, Any]:
        if self._portfolio:
            return self._portfolio._aggregate_risk()
        return {}

    def get_active_strategies(self) -> List[str]:
        if self._portfolio and self._portfolio._strategy_registry:
            return list(self._portfolio._strategy_registry.get_active().keys())
        return []

    # ─── Actions ───────────────────────────────────────────

    def orchestrator(self) -> Dict[str, Any]:
        if self._portfolio:
            return self._portfolio.orchestrate()
        return {"error": "No portfolio"}

    def net_signals(self) -> Dict[str, Any]:
        return self._submit_action("net_signals")

    def net_positions(self) -> Dict[str, Any]:
        return self._submit_action("net_positions")

    def rebalance(self) -> Dict[str, Any]:
        return self._submit_action("rebalance")

    def quarantine(self, strategy_id: str) -> Dict[str, Any]:
        return self._submit_action("quarantine", {"strategy_id": strategy_id})

    def replace(self, old_id: str, new_id: str) -> Dict[str, Any]:
        return self._submit_action("replace", {"old_id": old_id, "new_id": new_id})

    def _submit_action(self, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        if not self._controller:
            return {"error": "No controller"}
        from .portfolio_controller import ControllerCommand
        cmd = ControllerCommand(
            command_id=f"cmd-{uuid.uuid4().hex[:8]}",
            action=action,
            params=params or {},
        )
        result = self._controller.submit(cmd)
        return {"status": result.status, "output": result.output, "error": result.error}

    # ─── Events ────────────────────────────────────────────

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "portfolio_connected": self._portfolio is not None,
            "subscribers": len(self._subscribers),
        }
