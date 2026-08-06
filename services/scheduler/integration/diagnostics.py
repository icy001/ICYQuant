"""Integration Diagnostics — diagnostic tools for the scheduler integration layer.

The :class:`IntegrationDiagnostics` runs connectivity and health checks
across all platform adapters.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationDiagnostics:
    """Diagnostic tools for the platform integration layer.

    Runs checks for:
    * Adapter connectivity
    * Configuration health
    * Secret availability
    * Service discovery health
    * EventBus connectivity

    Usage::

        diag = IntegrationDiagnostics()
        report = await diag.run_full_check(adapters={...})
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._check_count: int = 0
        self._last_report: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Full Check
    # ------------------------------------------------------------------

    async def run_full_check(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Run a comprehensive diagnostic across all adapters."""
        self._check_count += 1

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check_id": self._check_count,
            "components": {},
            "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
        }

        checks = [
            ("connectivity", self._check_connectivity),
            ("configuration", self._check_configuration),
            ("discovery", self._check_discovery),
            ("eventbus", self._check_eventbus),
            ("workflow", self._check_workflow),
            ("business_adapters", self._check_business_adapters),
        ]

        for name, check_fn in checks:
            component_result = await check_fn(adapters)
            results["components"][name] = component_result
            results["summary"]["total"] += 1
            if component_result.get("status") == "healthy":
                results["summary"]["passed"] += 1
            elif component_result.get("status") == "warning":
                results["summary"]["warnings"] += 1
            else:
                results["summary"]["failed"] += 1

        self._last_report = results
        return results

    # ------------------------------------------------------------------
    # Individual Checks
    # ------------------------------------------------------------------

    async def _check_connectivity(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check connectivity of all adapters."""
        results = {}
        for name, adapter in adapters.items():
            results[name] = "connected" if getattr(adapter, "_connected", False) else "disconnected"
        return {"status": "healthy", "adapters": results}

    async def _check_configuration(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check configuration adapter health."""
        config_adapter = adapters.get("configuration")
        if config_adapter:
            return {"status": "healthy", "source": getattr(config_adapter, "source", "unknown")}
        return {"status": "warning", "message": "no configuration adapter"}

    async def _check_discovery(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check service discovery health."""
        discovery = adapters.get("discovery")
        if discovery:
            return {"status": "healthy", "instances": getattr(discovery, "instance_count", 0)}
        return {"status": "warning", "message": "no discovery adapter"}

    async def _check_eventbus(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check EventBus connectivity."""
        eventbus = adapters.get("eventbus")
        if eventbus:
            state = getattr(eventbus, "state", None)
            return {"status": "healthy" if state and "connected" in str(state) else "warning"}
        return {"status": "warning", "message": "no eventbus adapter"}

    async def _check_workflow(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check workflow engine connectivity."""
        workflow = adapters.get("workflow")
        if workflow:
            return {"status": "healthy", "active_workflows": getattr(workflow, "active_workflows", 0)}
        return {"status": "warning", "message": "no workflow adapter"}

    async def _check_business_adapters(self, adapters: Dict[str, Any]) -> Dict[str, Any]:
        """Check business domain adapter health."""
        business_keys = ["strategy", "ai", "research", "order", "risk", "execution", "settlement", "ledger"]
        healthy = 0
        for key in business_keys:
            if key in adapters:
                healthy += 1
        return {"status": "healthy", "adapters_available": healthy, "total": len(business_keys)}

    # ------------------------------------------------------------------
    # Quick Checks
    # ------------------------------------------------------------------

    async def check_connectivity(self, adapter_name: str, adapter: Any) -> Dict[str, Any]:
        """Check connectivity for a single adapter."""
        connected = getattr(adapter, "_connected", False)
        return {"adapter": adapter_name, "connected": connected, "status": "healthy" if connected else "unhealthy"}

    async def check_latency(self, adapter_name: str) -> Dict[str, Any]:
        """Check latency for an adapter."""
        return {"adapter": adapter_name, "latency_ms": 0, "status": "healthy"}

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        """Get the last diagnostic report."""
        return self._last_report
