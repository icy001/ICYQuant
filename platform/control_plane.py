"""
ICYQuant Platform - Unified Control Plane

Single control point for managing all platform modules.
Pause Trading → Risk Engine → Cancel Orders → Notify AI → Freeze Portfolio.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ControlPlane:
    """
    Unified control plane for the platform.

    Provides a single interface to control all modules:
    - Pause/resume trading
    - Trigger risk assessments
    - Broadcast notifications
    - Freeze/unfreeze portfolio
    - Emergency shutdown
    """

    def __init__(
        self,
        registry=None,
        runtime=None,
        event_router=None,
        orchestrator=None,
    ):
        self._registry = registry
        self._runtime = runtime
        self._event_router = event_router
        self._orchestrator = orchestrator
        self._control_log: List[Dict] = []

    def pause_trading(self, reason: str = "manual") -> Dict[str, Any]:
        """Pause all trading-related modules."""
        trading_modules = self._get_modules_by_type("trading")
        risk_modules = self._get_modules_by_type("risk")

        paused = []
        if self._runtime:
            for mod in trading_modules + risk_modules:
                if self._runtime.pause_module(mod):
                    paused.append(mod)

        if self._event_router:
            self._event_router.publish(
                "control.trading.paused",
                payload={"reason": reason, "modules": paused},
                source="control_plane",
            )

        self._log_action("pause_trading", reason, paused)
        return {"paused": paused}

    def resume_trading(self, reason: str = "manual") -> Dict[str, Any]:
        """Resume all trading-related modules."""
        result = {"resumed": []}
        if self._runtime:
            for mod in self._get_modules_by_type("trading"):
                if self._runtime.resume_module(mod):
                    result["resumed"].append(mod)

        if self._event_router:
            self._event_router.publish(
                "control.trading.resumed",
                payload={"reason": reason, "modules": result["resumed"]},
                source="control_plane",
            )

        self._log_action("resume_trading", reason, result["resumed"])
        return result

    def cancel_all_orders(self, reason: str = "emergency") -> Dict[str, Any]:
        """Cancel all active orders across OMS."""
        if self._event_router:
            self._event_router.publish(
                "control.orders.cancel_all",
                payload={"reason": reason},
                source="control_plane",
                priority=3,
            )

        self._log_action("cancel_all_orders", reason, [])
        return {"cancelled": True, "reason": reason}

    def notify_ai(self, message: str, severity: str = "info") -> Dict[str, Any]:
        """Send notification to AI modules."""
        if self._event_router:
            self._event_router.publish(
                "control.ai.notification",
                payload={"message": message, "severity": severity},
                source="control_plane",
            )

        self._log_action("notify_ai", message, [])
        return {"notified": True}

    def freeze_portfolio(self, reason: str = "risk") -> Dict[str, Any]:
        """Freeze portfolio rebalancing and modifications."""
        portfolio_modules = self._get_modules_by_type("portfolio")
        frozen = []
        if self._runtime:
            for mod in portfolio_modules:
                if self._runtime.pause_module(mod):
                    frozen.append(mod)

        if self._event_router:
            self._event_router.publish(
                "control.portfolio.frozen",
                payload={"reason": reason, "modules": frozen},
                source="control_plane",
                priority=2,
            )

        self._log_action("freeze_portfolio", reason, frozen)
        return {"frozen": frozen}

    def emergency_shutdown(self, reason: str = "critical") -> Dict[str, Any]:
        """Full platform emergency shutdown sequence."""
        sequence = [
            self.pause_trading,
            self.cancel_all_orders,
            lambda: self.notify_ai("Emergency shutdown initiated", "critical"),
            self.freeze_portfolio,
        ]

        results = {}
        for action in sequence:
            try:
                result = action(reason)
                results[action.__name__ if hasattr(action, '__name__') else str(action)] = result
            except Exception as e:
                results[str(action)] = {"error": str(e)}

        self._log_action("emergency_shutdown", reason, results)
        return {"shutdown": results}

    def module_command(self, module_type: str, command: str, **kwargs) -> Dict[str, Any]:
        """Send a command to all modules of a given type."""
        modules = self._get_modules_by_type(module_type)
        results = {}

        for mod in modules:
            if command == "status":
                rt = self._runtime.get_runtime(mod) if self._runtime else None
                results[mod] = rt.to_dict() if rt else {"state": "unknown"}
            elif command == "restart" and self._runtime:
                results[mod] = self._runtime.restart_module(mod)
            elif command == "pause" and self._runtime:
                results[mod] = self._runtime.pause_module(mod)
            elif command == "resume" and self._runtime:
                results[mod] = self._runtime.resume_module(mod)

        if self._event_router:
            self._event_router.publish(
                f"control.{module_type}.{command}",
                payload={"modules": modules, "kwargs": kwargs},
                source="control_plane",
            )

        return results

    def _get_modules_by_type(self, module_type: str) -> List[str]:
        if not self._registry:
            return []
        from .module_registry import ModuleType
        try:
            mt = ModuleType(module_type)
        except ValueError:
            return []
        return [m.name for m in self._registry.get_by_type(mt)]

    def _log_action(self, action: str, reason: str, results: Any):
        self._control_log.append({
            "action": action,
            "reason": reason,
            "results": str(results),
            "timestamp": datetime.now().isoformat(),
        })

    def get_log(self, limit: int = 50) -> List[Dict]:
        return self._control_log[-limit:]

    def get_status(self) -> Dict:
        return {
            "totalActions": len(self._control_log),
            "recentActions": len(self._control_log[-10:]),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
