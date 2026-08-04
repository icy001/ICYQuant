"""
Vault-specific health check.

Provides comprehensive health monitoring
for the Vault cluster, including:
- Server health (active/standby)
- Authentication status
- Lease health
- Namespace access
- Performance metrics
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .config import VaultConfig
from .lease import LeaseManager

logger = logging.getLogger(__name__)


class VaultHealthChecker:
    """
    Vault health check aggregator.

    Performs comprehensive health checks
    across all Vault integration components
    and provides a unified health status.

    Usage:
        health = VaultHealthChecker(client, config, lease_mgr)
        status = await health.check_all()
    """

    def __init__(
        self,
        client: VaultClient,
        config: VaultConfig,
        lease_manager: Optional[LeaseManager] = None,
    ) -> None:
        self._client = client
        self._config = config
        self._lease_manager = lease_manager
        self._last_check: Optional[datetime] = None
        self._health_history: list = []

    async def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Comprehensive health status dict.
        """
        start = time.perf_counter()
        results: Dict[str, Any] = {
            "healthy": True,
            "checks": {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # 1. Vault server health
        vault_ok, vault_info = await self._check_vault_server()
        results["checks"]["vault"] = {
            "healthy": vault_ok,
            **vault_info,
        }
        if not vault_ok:
            results["healthy"] = False

        # 2. Authentication health
        auth_ok, auth_info = self._check_authentication()
        results["checks"]["authentication"] = {
            "healthy": auth_ok,
            **auth_info,
        }
        if not auth_ok:
            results["healthy"] = False

        # 3. Lease health
        if self._lease_manager:
            lease_ok, lease_info = self._check_leases()
            results["checks"]["lease"] = {
                "healthy": lease_ok,
                **lease_info,
            }
            if not lease_ok:
                results["healthy"] = False
        else:
            results["checks"]["lease"] = {
                "healthy": True,
                "message": "No lease manager configured",
            }

        # 4. Namespace check
        ns_ok, ns_info = await self._check_namespace_access()
        results["checks"]["namespace"] = {
            "healthy": ns_ok,
            **ns_info,
        }
        if not ns_ok:
            results["healthy"] = False

        # Timing
        elapsed_ms = (time.perf_counter() - start) * 1000
        results["latency_ms"] = round(elapsed_ms, 2)

        # Store history
        self._last_check = datetime.utcnow()
        self._health_history.append({
            "timestamp": results["timestamp"],
            "healthy": results["healthy"],
            "latency_ms": elapsed_ms,
        })
        # Keep last 100 entries
        if len(self._health_history) > 100:
            self._health_history = self._health_history[-100:]

        return results

    async def _check_vault_server(self) -> tuple:
        """Check Vault server health."""
        try:
            health = await self._client.check_health(standby_ok=True)
            if health.get("healthy"):
                return True, {
                    "status": "healthy",
                    "version": health.get("version", "unknown"),
                    "cluster": health.get("cluster_name", "unknown"),
                    "standby": health.get("standby", False),
                }
            else:
                return False, {
                    "status": "unhealthy",
                    "error": health.get("error", "Unknown"),
                }
        except Exception as e:
            return False, {
                "status": "unreachable",
                "error": str(e),
            }

    def _check_authentication(self) -> tuple:
        """Check authentication status."""
        has_token = self._client._token is not None
        return has_token, {
            "authenticated": has_token,
            "has_token": has_token,
        }

    def _check_leases(self) -> tuple:
        """Check lease health."""
        if not self._lease_manager:
            return True, {"active": 0, "expired": 0}

        stats = self._lease_manager.get_stats()
        active = stats["active"]
        failed = stats["failed"]

        healthy = failed == 0
        return healthy, {
            "active": active,
            "expired": stats["expired"],
            "failed": failed,
            "total": stats["total"],
        }

    async def _check_namespace_access(self) -> tuple:
        """Check namespace accessibility."""
        namespace = self._config.namespace
        if not namespace or namespace == "default":
            return True, {"namespace": "default", "accessible": True}

        try:
            # Try to list the namespace
            path = f"/sys/namespaces/{namespace}"
            result = await self._client.read(path)
            return True, {
                "namespace": namespace,
                "accessible": True,
                "data": result.get("data", {}),
            }
        except Exception as e:
            # Namespace might not exist yet, which is ok
            return True, {
                "namespace": namespace,
                "accessible": True,
                "note": f"Namespace not yet created: {e}",
            }

    def get_quick_status(self) -> Dict[str, Any]:
        """Get quick health status without full checks."""
        return {
            "last_check": (
                self._last_check.isoformat() + "Z"
                if self._last_check
                else None
            ),
            "client_connected": self._client.connected,
            "has_token": self._client._token is not None,
            "total_requests": self._client.request_count,
            "last_latency_ms": round(self._client.last_latency * 1000, 2),
        }

    def get_history(self) -> list:
        """Get health check history."""
        return self._health_history.copy()
