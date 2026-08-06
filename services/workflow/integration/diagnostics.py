"""Integration Diagnostics — inspection and troubleshooting for platform integrations.

Provides tools for:
* Integration status overview
* Adapter health summary
* Connection diagnostics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


class IntegrationDiagnostics:
    """Diagnostic tools for platform integrations."""

    async def full_diagnostic(self, integration_manager) -> Dict[str, Any]:
        """Run a full diagnostic across all integration adapters."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "adapters": integration_manager.list_adapters(),
            "health": integration_manager.health_report(),
        }

    async def check_adapter(self, adapter) -> Dict[str, Any]:
        """Check health of a single adapter."""
        try:
            return {"healthy": True, "report": adapter.health_report()}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
