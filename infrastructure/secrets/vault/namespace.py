"""
Vault Namespace management.

Provides namespace isolation for
multi-tenant and multi-environment
Vault deployments.

Supported:
- Production / Staging / Development
- Trading / Risk / Research / Backtest isolation
- Tenant-level namespace separation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .client import VaultClient
from .config import VaultConfig
from .exceptions import VaultNamespaceError

logger = logging.getLogger(__name__)


# Standard namespace templates
PRODUCTION_NAMESPACES = [
    "icyquant/production/trading",
    "icyquant/production/risk",
    "icyquant/production/research",
    "icyquant/production/backtest",
]

STAGING_NAMESPACES = [
    "icyquant/staging/trading",
    "icyquant/staging/risk",
    "icyquant/staging/research",
    "icyquant/staging/backtest",
]

DEVELOPMENT_NAMESPACES = [
    "icyquant/development/trading",
    "icyquant/development/risk",
    "icyquant/development/research",
    "icyquant/development/backtest",
]

TENANT_NAMESPACE_TEMPLATE = "icyquant/tenants/{tenant_id}"


class VaultNamespaceManager:
    """
    Vault namespace management.

    Creates, configures, and manages Vault
    namespaces for environment and tenant
    isolation.

    Usage:
        ns_mgr = VaultNamespaceManager(client, config)
        await ns_mgr.create_namespace("icyquant/production/trading")
        namespaces = await ns_mgr.list_namespaces()
    """

    def __init__(
        self,
        client: VaultClient,
        config: VaultConfig,
    ) -> None:
        self._client = client
        self._config = config
        self._managed_namespaces: set = set()

    # ── Namespace Management ──

    async def create_namespace(
        self,
        path: str,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Vault namespace.

        Args:
            path: Namespace path (e.g., 'icyquant/production').
            custom_metadata: Additional metadata for the namespace.

        Returns:
            Creation response.
        """
        payload: Dict[str, Any] = {}
        if custom_metadata:
            payload["custom_metadata"] = custom_metadata

        # Use the /sys/namespaces endpoint
        ns_path = f"/sys/namespaces/{path.lstrip('/')}"
        result = await self._client.write(ns_path, payload=payload)
        self._managed_namespaces.add(path)
        logger.info("Namespace created: %s", path)
        return result

    async def delete_namespace(
        self,
        path: str,
    ) -> Dict[str, Any]:
        """
        Delete a Vault namespace.

        Args:
            path: Namespace path to delete.
        """
        ns_path = f"/sys/namespaces/{path.lstrip('/')}"
        result = await self._client.delete(ns_path)
        self._managed_namespaces.discard(path)
        logger.info("Namespace deleted: %s", path)
        return result

    async def list_namespaces(
        self,
        parent: str = "",
    ) -> List[Dict[str, Any]]:
        """
        List Vault namespaces.

        Args:
            parent: Parent namespace path.

        Returns:
            List of namespace info dicts.
        """
        ns_path = "/sys/namespaces"
        if parent:
            ns_path = f"/sys/namespaces/{parent.lstrip('/')}"

        try:
            result = await self._client.list(ns_path)
            return result.get("data", {}).get("keys", [])
        except Exception:
            return []

    async def read_namespace(
        self,
        path: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Read namespace details.

        Args:
            path: Namespace path.

        Returns:
            Namespace details or None.
        """
        ns_path = f"/sys/namespaces/{path.lstrip('/')}"
        try:
            result = await self._client.read(ns_path)
            return result.get("data")
        except Exception:
            return None

    async def update_namespace(
        self,
        path: str,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update namespace metadata.

        Args:
            path: Namespace path.
            custom_metadata: New metadata.
        """
        payload: Dict[str, Any] = {}
        if custom_metadata:
            payload["custom_metadata"] = custom_metadata

        ns_path = f"/sys/namespaces/{path.lstrip('/')}"
        return await self._client.write(ns_path, payload=payload)

    # ── Environment Setup ──

    async def setup_environment(
        self,
        environment: str = "production",
    ) -> List[str]:
        """
        Set up all namespaces for an environment.

        Args:
            environment: Environment name.

        Returns:
            List of created namespace paths.
        """
        if environment == "production":
            namespaces = PRODUCTION_NAMESPACES
        elif environment == "staging":
            namespaces = STAGING_NAMESPACES
        elif environment == "development":
            namespaces = DEVELOPMENT_NAMESPACES
        else:
            namespaces = [
                f"icyquant/{environment}/{ns}"
                for ns in ["trading", "risk", "research", "backtest"]
            ]

        created = []
        for ns_path in namespaces:
            try:
                await self.create_namespace(
                    ns_path,
                    custom_metadata={
                        "environment": environment,
                        "managed_by": "icyquant",
                    },
                )
                created.append(ns_path)
            except Exception as e:
                logger.warning(
                    "Failed to create namespace %s: %s", ns_path, e
                )

        logger.info(
            "Environment '%s' setup: %d/%d namespaces created",
            environment,
            len(created),
            len(namespaces),
        )
        return created

    async def setup_tenant(
        self,
        tenant_id: str,
        environments: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Set up namespaces for a tenant.

        Args:
            tenant_id: Tenant identifier.
            environments: Environments to set up.

        Returns:
            List of created namespace paths.
        """
        if environments is None:
            environments = ["production", "staging", "development"]

        created = []
        for env in environments:
            ns_base = TENANT_NAMESPACE_TEMPLATE.format(tenant_id=tenant_id)
            for area in ["trading", "risk", "research", "backtest"]:
                ns_path = f"{ns_base}/{env}/{area}"
                try:
                    await self.create_namespace(
                        ns_path,
                        custom_metadata={
                            "tenant_id": tenant_id,
                            "environment": env,
                            "area": area,
                            "managed_by": "icyquant",
                        },
                    )
                    created.append(ns_path)
                except Exception as e:
                    logger.warning(
                        "Failed to create tenant namespace %s: %s",
                        ns_path,
                        e,
                    )

        return created

    # ── Status ──

    def get_managed_namespaces(self) -> set:
        """Get set of managed namespace paths."""
        return self._managed_namespaces.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get namespace manager statistics."""
        return {
            "managed_count": len(self._managed_namespaces),
            "managed": sorted(self._managed_namespaces),
        }
