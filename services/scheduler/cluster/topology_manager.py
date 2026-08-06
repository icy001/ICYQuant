"""Cluster Topology Manager — maintains the physical/logical topology of the scheduler cluster.

The :class:`ClusterTopologyManager` tracks the hierarchical structure of
the scheduler cluster (Region → Zone → Rack → Node) and enables
topology-aware scheduling decisions that minimize cross-zone latency.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ClusterDomain:
    """Enumeration of topology domain levels."""

    REGION = "region"
    ZONE = "zone"
    RACK = "rack"
    NODE = "node"


class ClusterTopologyManager:
    """Maintains the hierarchical topology of the scheduler cluster.

    Hierarchy::

        Region
          └── Zone
                └── Rack
                      └── Node (scheduler instance)

    Topology awareness enables:
    - Local-first scheduling (prefer same-zone workers)
    - Fault-domain aware placement (anti-affinity across racks)
    - Cross-region latency estimation

    Usage::

        topo = ClusterTopologyManager()
        await topo.start()
        topo.add_node("scheduler-1", region="us-east", zone="us-east-1a", rack="r01")
        nearby = topo.get_nodes_in_zone("us-east-1a")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_running = False

        # Topology data
        self._regions: Dict[str, Set[str]] = {}  # region → zones
        self._zones: Dict[str, Dict[str, Set[str]]] = {}  # zone → {region, racks}
        self._racks: Dict[str, Dict[str, Any]] = {}  # rack → {zone, region, nodes}
        self._node_locations: Dict[str, Dict[str, str]] = {}  # node_id → {region, zone, rack}

        # Latency estimates (ms)
        self._latency_matrix: Dict[str, Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._node_locations)

    @property
    def region_count(self) -> int:
        with self._lock:
            return len(self._regions)

    @property
    def zone_count(self) -> int:
        with self._lock:
            return len(self._zones)

    @property
    def rack_count(self) -> int:
        with self._lock:
            return len(self._racks)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the topology manager."""
        self._is_running = True
        logger.info("Cluster topology manager started")

    async def stop(self) -> None:
        """Stop the topology manager."""
        self._is_running = False
        logger.info("Cluster topology manager stopped")

    async def sync(self) -> None:
        """Synchronize topology state across the cluster."""
        logger.debug("Topology sync requested [nodes=%d]", self.node_count)

    # ------------------------------------------------------------------
    # Node Placement
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        *,
        region: str = "default",
        zone: str = "default",
        rack: str = "default",
    ) -> None:
        """Add a node to the topology.

        Args:
            node_id: Scheduler node ID.
            region: Region identifier (e.g., "us-east").
            zone: Availability zone (e.g., "us-east-1a").
            rack: Physical rack identifier.
        """
        with self._lock:
            # Register hierarchy
            self._regions.setdefault(region, set()).add(zone)
            self._zones.setdefault(zone, {"region": region, "racks": set()})
            self._zones[zone]["racks"].add(rack)
            self._racks.setdefault(rack, {"zone": zone, "region": region, "nodes": set()})
            self._racks[rack]["nodes"].add(node_id)

            # Node location
            self._node_locations[node_id] = {
                "region": region,
                "zone": zone,
                "rack": rack,
            }

        logger.debug("Node %s added to topology [region=%s, zone=%s, rack=%s]",
                      node_id, region, zone, rack)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the topology."""
        with self._lock:
            location = self._node_locations.pop(node_id, None)
            if location:
                rack = location["rack"]
                if rack in self._racks:
                    self._racks[rack]["nodes"].discard(node_id)
                    if not self._racks[rack]["nodes"]:
                        zone = self._racks[rack]["zone"]
                        if zone in self._zones:
                            self._zones[zone]["racks"].discard(rack)
                        del self._racks[rack]
        logger.debug("Node %s removed from topology", node_id)

    # ------------------------------------------------------------------
    # Location Queries
    # ------------------------------------------------------------------

    def get_location(self, node_id: str) -> Optional[Dict[str, str]]:
        """Get the topological location of a node."""
        with self._lock:
            return dict(self._node_locations.get(node_id, {}))

    def get_nodes_in_region(self, region: str) -> List[str]:
        """Get all nodes in a region."""
        nodes = []
        with self._lock:
            zones = self._regions.get(region, set())
            for zone in zones:
                zone_info = self._zones.get(zone, {})
                for rack in zone_info.get("racks", set()):
                    nodes.extend(self._racks.get(rack, {}).get("nodes", set()))
        return nodes

    def get_nodes_in_zone(self, zone: str) -> List[str]:
        """Get all nodes in an availability zone."""
        nodes = []
        with self._lock:
            zone_info = self._zones.get(zone, {})
            for rack in zone_info.get("racks", set()):
                nodes.extend(self._racks.get(rack, {}).get("nodes", set()))
        return nodes

    def get_nodes_in_rack(self, rack: str) -> List[str]:
        """Get all nodes in a physical rack."""
        with self._lock:
            return list(self._racks.get(rack, {}).get("nodes", set()))

    def get_peers_in_same_zone(self, node_id: str) -> List[str]:
        """Get peer nodes in the same zone (excluding self)."""
        location = self.get_location(node_id)
        if not location:
            return []
        peers = self.get_nodes_in_zone(location["zone"])
        return [p for p in peers if p != node_id]

    def get_peers_in_different_zone(self, node_id: str) -> List[str]:
        """Get peer nodes in different zones (for anti-affinity)."""
        location = self.get_location(node_id)
        if not location:
            return []
        zone = location["zone"]
        all_nodes = list(self._node_locations.keys())
        return [n for n in all_nodes if self._node_locations.get(n, {}).get("zone") != zone]

    # ------------------------------------------------------------------
    # Topology Distance
    # ------------------------------------------------------------------

    def get_distance(self, node_a: str, node_b: str) -> int:
        """Get the topological distance between two nodes.

        Returns:
            0 = same rack, 1 = same zone diff rack, 2 = same region diff zone, 3 = diff region.
        """
        loc_a = self.get_location(node_a)
        loc_b = self.get_location(node_b)
        if not loc_a or not loc_b:
            return 3

        if loc_a["rack"] == loc_b["rack"]:
            return 0
        if loc_a["zone"] == loc_b["zone"]:
            return 1
        if loc_a["region"] == loc_b["region"]:
            return 2
        return 3

    def estimate_latency_ms(self, node_a: str, node_b: str) -> float:
        """Estimate network latency between two nodes based on topology.

        Rough estimates:
        - Same rack: 0.1ms
        - Same zone: 1ms
        - Same region: 5ms
        - Different region: 50ms
        """
        distance = self.get_distance(node_a, node_b)
        latency_map = {0: 0.1, 1: 1.0, 2: 5.0, 3: 50.0}
        return latency_map.get(distance, 100.0)

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def get_topology_summary(self) -> Dict[str, Any]:
        """Return a topology summary."""
        with self._lock:
            return {
                "regions": list(self._regions.keys()),
                "zone_count": len(self._zones),
                "rack_count": len(self._racks),
                "node_count": len(self._node_locations),
                "topology": {
                    region: {
                        "zones": list(zones),
                    }
                    for region, zones in self._regions.items()
                },
            }

    def get_topology_info(self) -> Dict[str, Any]:
        """Return full topology status."""
        return self.get_topology_summary()
