"""Topology Manager — cluster topology awareness for placement decisions.

The :class:`TopologyManager` models the physical hierarchy of the cluster
(Region → Zone → Rack → Node) and provides helpers to prefer nodes in
the same topological domain, minimizing cross-region latency and costs.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class TopologyDomain(str, enum.Enum):
    RACK = "rack"
    ZONE = "zone"
    REGION = "region"
    CLUSTER = "cluster"
    EDGE = "edge"


@dataclass
class TopologyNode:
    """A node in the topology tree."""

    node_id: str
    domain: TopologyDomain = TopologyDomain.CLUSTER
    region: str = ""
    zone: str = ""
    rack: str = ""
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)

    @property
    def location_path(self) -> str:
        return f"{self.region}/{self.zone}/{self.rack}"


class TopologyManager:
    """Manages cluster topology for scheduling decisions.

    Usage::

        topo = TopologyManager()
        topo.register_node("node-1", region="us-east", zone="us-east-1a", rack="r01")
        nearby = topo.get_nodes_in_same_zone("node-1")  # → ["node-1", "node-2"]
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, TopologyNode] = {}
        # region → zone → rack → [node_ids]
        self._index: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_node(
        self, node_id: str, region: str = "default",
        zone: str = "default", rack: str = "default",
    ) -> None:
        node = TopologyNode(
            node_id=node_id, domain=TopologyDomain.CLUSTER,
            region=region, zone=zone, rack=rack,
        )
        self._nodes[node_id] = node

        # Build index
        self._index.setdefault(region, {}).setdefault(zone, {}).setdefault(rack, []).append(node_id)

    def unregister_node(self, node_id: str) -> None:
        node = self._nodes.pop(node_id, None)
        if node is None:
            return
        rack_list = (
            self._index.get(node.region, {})
            .get(node.zone, {})
            .get(node.rack, [])
        )
        if node_id in rack_list:
            rack_list.remove(node_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_node_domain(self, node_id: str) -> Optional[str]:
        """Return the location path of a node."""
        node = self._nodes.get(node_id)
        return node.location_path if node else None

    def get_nodes_in_same_rack(self, node_id: str) -> List[str]:
        node = self._nodes.get(node_id)
        if node is None:
            return []
        return list(
            self._index.get(node.region, {})
            .get(node.zone, {})
            .get(node.rack, [])
        )

    def get_nodes_in_same_zone(self, node_id: str) -> List[str]:
        node = self._nodes.get(node_id)
        if node is None:
            return []
        result: List[str] = []
        for rack_list in (
            self._index.get(node.region, {}).get(node.zone, {}).values()
        ):
            result.extend(rack_list)
        return result

    def get_nodes_in_region(self, region: str) -> List[str]:
        result: List[str] = []
        for zone_dict in self._index.get(region, {}).values():
            for rack_list in zone_dict.values():
                result.extend(rack_list)
        return result

    def get_preferred_nodes(
        self, job_id: str = "", region: Optional[str] = None,
        zone: Optional[str] = None,
    ) -> List[str]:
        """Get nodes preferred by topology (same region/zone)."""
        if region and zone:
            result: List[str] = []
            for rack_list in (
                self._index.get(region, {}).get(zone, {}).values()
            ):
                result.extend(rack_list)
            return result
        if region:
            return self.get_nodes_in_region(region)
        # Return all nodes sorted by proximity
        all_nodes: List[str] = []
        for region_dict in self._index.values():
            for zone_dict in region_dict.values():
                for rack_list in zone_dict.values():
                    all_nodes.extend(rack_list)
        return all_nodes

    # ------------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------------

    def estimate_latency_ms(self, node_a: str, node_b: str) -> float:
        """Estimate latency between two nodes based on topology distance.

        Approximate costs:
        * Same rack: 1ms
        * Same zone: 3ms
        * Same region: 10ms
        * Cross-region: 50ms
        """
        a = self._nodes.get(node_a)
        b = self._nodes.get(node_b)
        if a is None or b is None:
            return 100.0
        if a.region != b.region:
            return 50.0
        if a.zone != b.zone:
            return 10.0
        if a.rack != b.rack:
            return 3.0
        return 1.0

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_regions(self) -> List[str]:
        return list(self._index.keys())

    def list_zones(self, region: str) -> List[str]:
        return list(self._index.get(region, {}).keys())

    def list_racks(self, region: str, zone: str) -> List[str]:
        return list(self._index.get(region, {}).get(zone, {}).keys())

    def node_count(self) -> int:
        return len(self._nodes)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "regions": self.list_regions(),
            "zones_per_region": {
                r: self.list_zones(r) for r in self.list_regions()
            },
        }
