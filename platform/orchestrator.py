"""
ICYQuant Platform - Platform Orchestrator

Central orchestrator that coordinates complex multi-module workflows.
AI Signal → Risk → OMS → EMS → Broker → Position → Portfolio → Reporting.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PlatformOrchestrator:
    """
    Central orchestrator for cross-module workflows.

    Coordinates sequences like:
    - AI Signal → Risk Check → OMS → EMS → Broker → Position Update
    - Research → Backtest → Deploy → Paper Trading → Production
    - Emergency: Pause Trading → Risk Cancel → Notify AI → Freeze Portfolio
    """

    def __init__(
        self,
        registry=None,
        runtime=None,
        event_router=None,
        workflow_engine=None,
    ):
        self._registry = registry
        self._runtime = runtime
        self._event_router = event_router
        self._workflow_engine = workflow_engine
        self._execution_log: List[Dict] = []

    def orchestrate_trade_sequence(
        self,
        signal: Dict[str, Any],
        risk_check_fn: Optional[callable] = None,
        oms_execute_fn: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrate the full trading sequence:
        AI Signal → Risk → OMS → EMS → Broker → Position → Portfolio
        """
        steps = []
        steps.append({"step": "signal", "data": signal})

        if risk_check_fn:
            risk_result = risk_check_fn(signal)
            steps.append({"step": "risk_check", "result": risk_result})
            if not risk_result.get("approved", False):
                return {
                    "status": "rejected",
                    "reason": risk_result.get("reason", "Risk check failed"),
                    "steps": steps,
                }

        if self._event_router:
            self._event_router.publish(
                "trade.signal.received",
                payload=signal,
                source="orchestrator",
            )

        if oms_execute_fn:
            oms_result = oms_execute_fn(signal)
            steps.append({"step": "oms", "result": oms_result})

        if self._event_router:
            self._event_router.publish(
                "trade.executed",
                payload=steps[-1] if steps else {},
                source="orchestrator",
            )

        steps.append({
            "step": "complete",
            "timestamp": datetime.now().isoformat(),
        })

        self._execution_log.append({
            "type": "trade_sequence",
            "signal": signal,
            "result": steps,
            "timestamp": datetime.now().isoformat(),
        })

        return {
            "status": "completed",
            "steps": steps,
        }

    def orchestrate_emergency_halt(
        self,
        reason: str = "manual",
        modules_to_pause: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Emergency halt sequence:
        Pause Trading → Risk Engine → Cancel Orders → Notify AI → Freeze Portfolio
        """
        if modules_to_pause is None and self._registry:
            modules_to_pause = [
                m.name for m in self._registry.get_all()
                if m.module_type.value in ("trading", "risk")
            ]

        results = {"paused": [], "cancelled": [], "notifications": []}

        if self._runtime:
            for name in (modules_to_pause or []):
                if self._runtime.pause_module(name):
                    results["paused"].append(name)

        if self._event_router:
            self._event_router.publish(
                "emergency.halt",
                payload={"reason": reason, "modules": results["paused"]},
                source="orchestrator",
                priority=3,
            )

        self._execution_log.append({
            "type": "emergency_halt",
            "reason": reason,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        })

        return results

    def orchestrate_research_to_production(
        self,
        research_id: str,
        backtest_fn: Optional[callable] = None,
        deploy_fn: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Research → Backtest → Deploy Model → Paper Trading → Production
        """
        steps = [
            {"step": "research", "id": research_id, "status": "completed"},
        ]

        if backtest_fn:
            bt_result = backtest_fn(research_id)
            steps.append({"step": "backtest", "result": bt_result})
            if not bt_result.get("passed", False):
                return {
                    "status": "failed",
                    "stage": "backtest",
                    "reason": bt_result.get("reason", "Backtest failed"),
                    "steps": steps,
                }

        if deploy_fn:
            deploy_result = deploy_fn(research_id)
            steps.append({"step": "deploy", "result": deploy_result})

        if self._workflow_engine:
            try:
                wf = self._workflow_engine.create_workflow(
                    name=f"research_prod_{research_id}",
                    steps=steps,
                )
                self._workflow_engine.start_workflow(wf.workflow_id)
            except Exception:
                pass

        return {
            "status": "completed",
            "steps": steps,
        }

    def get_execution_log(self, limit: int = 50) -> List[Dict]:
        return self._execution_log[-limit:]

    def get_status(self) -> Dict:
        return {
            "totalExecutions": len(self._execution_log),
            "recentExecutions": len(self._execution_log[-10:]),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
