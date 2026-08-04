"""
Vault Discovery service.

Discovers Vault cluster nodes and
determines optimal server selection
based on health, latency, and role
(active/standby).

Features:
- Cluster node discovery
- Active/standby detection
- Latency-based server selection
- Connection pooling optimization
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .vault.client import VaultClient
from .vault.config import VaultConfig

logger = logging.getLogger(__name__)


class VaultNode:
    """Represents a single Vault cluster node."""

    def __init__(
        self,
        address: str,
        node_id: str = "",
        role: str = "standby",
    ) -> None:
        self.address = address
        self.node_id = node_id
        self.role = role  # "active" or "standby"
        self.healthy = True
        self.latency_ms: float = 0.0
        self.last_check: Optional[datetime] = None
        self.fail_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "node_id": self.node_id,
            "role": self.role,
            "healthy": self.healthy,
            "latency_ms": round(self.latency_ms, 2),
            "last_check": (
                self.last_check.isoformat() + "Z"
                if self.last_check
                else None
            ),
            "fail_count": self.fail_count,
        }


class VaultDiscovery:
    """
    Vault cluster discovery service.

    Discovers Vault nodes, monitors their
    health, and selects optimal nodes
    for client connections.

    Usage:
        discovery = VaultDiscovery(config)
        await discovery.discover_cluster()
        best = discovery.get_best_node()
    """

    def __init__(
        self,
        config: VaultConfig,
    ) -> None:
        self._config = config
        self._nodes: List[VaultNode] = []
        self._active_node: Optional[VaultNode] = None
        self._standby_nodes: List[VaultNode] = []
        self._discovery_task: Optional[asyncio.Task] = None
        self._running = False

    async def discover_cluster(self) -> List[VaultNode]:
        """
        Discover all Vault cluster nodes.

        Probes the primary node and discovers
        standby nodes via the cluster API.

        Returns:
            List of discovered nodes.
        """
        nodes: List[VaultNode] = []

        # Check primary
        primary = VaultNode(
            address=self._config.address,
            role="active",
        )
        primary = await self._probe_node(primary)
        nodes.append(primary)

        self._active_node = primary if primary.healthy else None

        # Check standby nodes
        for standby_addr in self._config.failover.standby_addresses:
            node = VaultNode(address=standby_addr, role="standby")
            node = await self._probe_node(node)
            nodes.append(node)

        self._standby_nodes = [n for n in nodes if n.role == "standby"]
        self._nodes = nodes

        logger.info(
            "Discovered %d Vault nodes: %d healthy",
            len(nodes),
            sum(1 for n in nodes if n.healthy),
        )

        return nodes

    async def _probe_node(self, node: VaultNode) -> VaultNode:
        """
        Probe a single Vault node for health and latency.

        Args:
            node: Node to probe.

        Returns:
            Updated node.
        """
        try:
            config = VaultConfig(address=node.address)
            client = VaultClient(config)
            await client.connect()

            start = time.perf_counter()
            health = await client.check_health(standby_ok=True)
            latency = (time.perf_counter() - start) * 1000

            await client.disconnect()

            node.healthy = health.get("healthy", False)
            node.latency_ms = latency
            node.last_check = datetime.utcnow()

            if health.get("data", {}).get("standby", False):
                node.role = "standby"
            else:
                node.role = "active"

            node.fail_count = 0 if node.healthy else node.fail_count

        except Exception as e:
            node.healthy = False
            node.fail_count += 1
            node.last_check = datetime.utcnow()
            logger.warning(
                "Node probe failed: %s - %s", node.address, e
            )

        return node

    async def start_discovery_loop(
        self,
        interval: int = 30,
    ) -> None:
        """
        Start periodic discovery loop.

        Args:
            interval: Discovery interval in seconds.
        """
        if self._running:
            return

        self._running = True
        self._discovery_task = asyncio.create_task(
            self._discovery_loop(interval)
        )

    async def stop_discovery_loop(self) -> None:
        """Stop the discovery loop."""
        self._running = False
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None

    async def _discovery_loop(self, interval: int) -> None:
        """Background discovery loop."""
        while self._running:
            try:
                await self.discover_cluster()
            except Exception as e:
                logger.error("Discovery loop error: %s", e)
            await asyncio.sleep(interval)

    def get_active_node(self) -> Optional[VaultNode]:
        """Get the current active node."""
        if self._active_node and self._active_node.healthy:
            return self._active_node

        # Find healthy active
        for node in self._nodes:
            if node.role == "active" and node.healthy:
                self._active_node = node
                return node

        # Fall back to first healthy
        for node in self._nodes:
            if node.healthy:
                self._active_node = node
                return node

        return None

    def get_standby_nodes(self) -> List[VaultNode]:
        """Get healthy standby nodes."""
        return [n for n in self._standby_nodes if n.healthy]

    def get_best_node(self) -> Optional[VaultNode]:
        """
        Get the best node based on health and latency.

        Returns:
            Best node or None.
        """
        healthy = [n for n in self._nodes if n.healthy]
        if not healthy:
            return None

        # Prefer active node
        active = [n for n in healthy if n.role == "active"]
        if active:
            return min(active, key=lambda n: n.latency_ms)

        # Fall back to standby with lowest latency
        return min(healthy, key=lambda n: n.latency_ms)

    def get_all_nodes(self) -> List[VaultNode]:
        """Get all discovered nodes."""
        return self._nodes.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get discovery statistics."""
        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": sum(1 for n in self._nodes if n.healthy),
            "active_node": self._active_node.to_dict() if self._active_node else None,
            "running": self._running,
        }
