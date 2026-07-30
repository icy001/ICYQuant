"""
Knowledge Graph Engine.

Builds and queries entity relationship graphs:
- Company supply chain networks
- Industry value chains
- Technology dependency graphs
- Competition networks
- Cross-market relationships
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    COMPANY = "company"
    PRODUCT = "product"
    INDUSTRY = "industry"
    SECTOR = "sector"
    TECHNOLOGY = "technology"
    PERSON = "person"
    EVENT = "event"
    INDEX = "index"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    REGION = "region"


class EdgeType(str, Enum):
    SUPPLIER_OF = "supplier_of"
    CUSTOMER_OF = "customer_of"
    COMPETITOR_OF = "competitor_of"
    PARTNER_OF = "partner_of"
    OWNS = "owns"
    SUBSIDIARY_OF = "subsidiary_of"
    PRODUCES = "produces"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    REGULATES = "regulates"
    CORRELATED_WITH = "correlated_with"
    SUPPLY_CHAIN = "supply_chain"
    TECHNOLOGY_STACK = "technology_stack"
    RELATED_TO = "related_to"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    node_type: NodeType = NodeType.COMPANY

    # Attributes
    ticker: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: str = ""

    # Graph metrics
    degree: int = 0
    in_degree: int = 0
    out_degree: int = 0
    centrality: float = 0.0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "ticker": self.ticker,
            "sector": self.sector,
            "industry": self.industry,
            "description": self.description,
            "degree": self.degree,
            "centrality": self.centrality,
        }


@dataclass
class GraphEdge:
    """An edge (relationship) between two nodes."""

    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.RELATED_TO

    # Strength and confidence
    weight: float = 1.0
    confidence: float = 0.5

    # Description
    label: str = ""
    description: str = ""

    # Temporal
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Evidence
    evidence_sources: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "confidence": self.confidence,
            "label": self.label,
            "description": self.description,
        }


@dataclass
class GraphQuery:
    """Query parameters for graph traversal."""

    start_node: Optional[str] = None
    max_depth: int = 3
    edge_types: Optional[List[EdgeType]] = None
    node_types: Optional[List[NodeType]] = None
    min_weight: float = 0.0
    min_confidence: float = 0.0
    direction: str = "both"  # "outgoing", "incoming", "both"
    limit: int = 100


# ── Knowledge Graph ──────────────────────────────────────────────────────────

class KnowledgeGraph:
    """
    Entity knowledge graph for financial relationships.

    Supports:
    - Building company/industry/product relationship networks
    - Graph traversal (BFS, DFS)
    - Supply chain path discovery
    - Centrality computation
    - Subgraph extraction
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        # Adjacency: node_id → {target_id → [edge_ids]}
        self._adj_out: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._adj_in: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Name index
        self._name_index: Dict[str, str] = {}

    # ── Node Operations ──────────────────────────────────────────────────────

    def add_node(
        self,
        name: str,
        node_type: NodeType,
        ticker: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        description: str = "",
        **kwargs,
    ) -> GraphNode:
        """Add or update a node in the graph."""
        # Check if node already exists by name
        existing_id = self._name_index.get(name.lower())
        if existing_id and existing_id in self._nodes:
            node = self._nodes[existing_id]
            # Update attributes
            if ticker:
                node.ticker = ticker
            if sector:
                node.sector = sector
            if industry:
                node.industry = industry
            if description:
                node.description = description
            node.updated_at = datetime.now(timezone.utc)
            return node

        node = GraphNode(
            name=name,
            node_type=node_type,
            ticker=ticker,
            sector=sector,
            industry=industry,
            description=description,
            **kwargs,
        )
        self._nodes[node.node_id] = node
        self._name_index[name.lower()] = node.node_id
        return node

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID."""
        return self._nodes.get(node_id)

    def find_node(self, name: str) -> Optional[GraphNode]:
        """Find node by name."""
        node_id = self._name_index.get(name.lower())
        if node_id:
            return self._nodes.get(node_id)
        return None

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of a given type."""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        if node_id not in self._nodes:
            return False

        # Remove all edges connected to this node
        edges_to_remove = []
        for edge_id, edge in self._edges.items():
            if edge.source_id == node_id or edge.target_id == node_id:
                edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            self.remove_edge(edge_id)

        # Remove from name index
        node = self._nodes[node_id]
        self._name_index.pop(node.name.lower(), None)

        del self._nodes[node_id]
        return True

    # ── Edge Operations ──────────────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        confidence: float = 0.5,
        label: str = "",
        description: str = "",
        **kwargs,
    ) -> Optional[GraphEdge]:
        """Add a directed edge between two nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            logger.warning(
                f"Cannot add edge: source={source_id} or target={target_id} not found"
            )
            return None

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            confidence=confidence,
            label=label,
            description=description,
            **kwargs,
        )
        self._edges[edge.edge_id] = edge
        self._adj_out[source_id][target_id].append(edge.edge_id)
        self._adj_in[target_id][source_id].append(edge.edge_id)

        # Update node degrees
        self._nodes[source_id].out_degree += 1
        self._nodes[source_id].degree += 1
        self._nodes[target_id].in_degree += 1
        self._nodes[target_id].degree += 1

        return edge

    def add_bi_edge(
        self,
        node_a_id: str,
        node_b_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        confidence: float = 0.5,
        label: str = "",
    ) -> Tuple[Optional[GraphEdge], Optional[GraphEdge]]:
        """Add bidirectional edges between two nodes."""
        e1 = self.add_edge(node_a_id, node_b_id, edge_type, weight, confidence, label)
        e2 = self.add_edge(node_b_id, node_a_id, edge_type, weight, confidence, label)
        return e1, e2

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get edge by ID."""
        return self._edges.get(edge_id)

    def get_edges_between(
        self, source_id: str, target_id: str
    ) -> List[GraphEdge]:
        """Get all edges between two nodes."""
        edge_ids = self._adj_out.get(source_id, {}).get(target_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def remove_edge(self, edge_id: str) -> bool:
        """Remove an edge."""
        if edge_id not in self._edges:
            return False

        edge = self._edges[edge_id]

        # Remove from adjacency
        src_adj = self._adj_out.get(edge.source_id, {})
        if edge.target_id in src_adj and edge_id in src_adj[edge.target_id]:
            src_adj[edge.target_id].remove(edge_id)

        tgt_adj = self._adj_in.get(edge.target_id, {})
        if edge.source_id in tgt_adj and edge_id in tgt_adj[edge.source_id]:
            tgt_adj[edge.source_id].remove(edge_id)

        # Update degrees
        if edge.source_id in self._nodes:
            self._nodes[edge.source_id].out_degree = max(
                0, self._nodes[edge.source_id].out_degree - 1
            )
            self._nodes[edge.source_id].degree = max(
                0, self._nodes[edge.source_id].degree - 1
            )
        if edge.target_id in self._nodes:
            self._nodes[edge.target_id].in_degree = max(
                0, self._nodes[edge.target_id].in_degree - 1
            )
            self._nodes[edge.target_id].degree = max(
                0, self._nodes[edge.target_id].degree - 1
            )

        del self._edges[edge_id]
        return True

    # ── Graph Traversal ──────────────────────────────────────────────────────

    def get_neighbors(
        self,
        node_id: str,
        edge_types: Optional[List[EdgeType]] = None,
        direction: str = "both",
    ) -> List[Tuple[GraphNode, GraphEdge]]:
        """Get neighbors of a node."""
        if node_id not in self._nodes:
            return []

        neighbors: List[Tuple[GraphNode, GraphEdge]] = []

        # Outgoing
        if direction in ("outgoing", "both"):
            for tgt_id, edge_ids in self._adj_out.get(node_id, {}).items():
                for eid in edge_ids:
                    edge = self._edges.get(eid)
                    if edge and (not edge_types or edge.edge_type in edge_types):
                        tgt_node = self._nodes.get(tgt_id)
                        if tgt_node:
                            neighbors.append((tgt_node, edge))

        # Incoming
        if direction in ("incoming", "both"):
            for src_id, edge_ids in self._adj_in.get(node_id, {}).items():
                for eid in edge_ids:
                    edge = self._edges.get(eid)
                    if edge and (not edge_types or edge.edge_type in edge_types):
                        src_node = self._nodes.get(src_id)
                        if src_node:
                            neighbors.append((src_node, edge))

        return neighbors

    def bfs(
        self,
        start_id: str,
        max_depth: int = 3,
        edge_types: Optional[List[EdgeType]] = None,
        direction: str = "outgoing",
    ) -> Dict[int, List[str]]:
        """
        Breadth-first search from a start node.

        Args:
            start_id: Starting node ID.
            max_depth: Maximum traversal depth.
            edge_types: Optional filter for edge types.
            direction: "outgoing", "incoming", or "both".

        Returns:
            Dict mapping depth → list of node IDs at that depth.
        """
        if start_id not in self._nodes:
            return {}

        visited: Set[str] = {start_id}
        levels: Dict[int, List[str]] = {0: [start_id]}
        queue: deque = deque([(start_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Collect neighbors based on direction
            neighbor_ids: Set[str] = set()
            if direction in ("outgoing", "both"):
                neighbor_ids.update(self._adj_out.get(current, {}).keys())
            if direction in ("incoming", "both"):
                neighbor_ids.update(self._adj_in.get(current, {}).keys())

            for tgt_id in neighbor_ids:
                if tgt_id in visited:
                    continue

                # Filter by edge types across both directions
                valid = True
                if edge_types:
                    valid = False
                    for adj in (
                        [self._adj_out] if direction == "outgoing"
                        else [self._adj_in] if direction == "incoming"
                        else [self._adj_out, self._adj_in]
                    ):
                        for eid in adj.get(current, {}).get(tgt_id, []):
                            if self._edges.get(eid) and self._edges[eid].edge_type in edge_types:
                                valid = True
                                break
                        if valid:
                            break

                if not valid:
                    continue

                visited.add(tgt_id)
                new_depth = depth + 1
                if new_depth not in levels:
                    levels[new_depth] = []
                levels[new_depth].append(tgt_id)
                queue.append((tgt_id, new_depth))

        return levels

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        max_paths: int = 10,
    ) -> List[List[str]]:
        """Find all paths between two nodes up to max_depth."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        paths: List[List[str]] = []
        stack = [(source_id, [source_id], set([source_id]))]

        while stack and len(paths) < max_paths:
            current, path, visited = stack.pop()

            if len(path) > max_depth:
                continue

            for tgt_id in self._adj_out.get(current, {}):
                if tgt_id == target_id:
                    paths.append(path + [tgt_id])
                    if len(paths) >= max_paths:
                        break
                elif tgt_id not in visited:
                    stack.append((tgt_id, path + [tgt_id], visited | {tgt_id}))

        return paths

    # ── Centrality ───────────────────────────────────────────────────────────

    def compute_degree_centrality(self) -> Dict[str, float]:
        """Compute degree centrality for all nodes."""
        n = len(self._nodes)
        if n <= 1:
            return {nid: 0.0 for nid in self._nodes}

        centrality = {}
        for nid, node in self._nodes.items():
            centrality[nid] = node.degree / (n - 1)
            node.centrality = centrality[nid]

        return centrality

    def get_most_central(self, k: int = 10) -> List[Tuple[GraphNode, float]]:
        """Get k most central nodes by degree."""
        centrality = self.compute_degree_centrality()
        sorted_nodes = sorted(
            centrality.items(), key=lambda x: x[1], reverse=True
        )
        return [
            (self._nodes[nid], score)
            for nid, score in sorted_nodes[:k]
            if nid in self._nodes
        ]

    # ── Subgraph Extraction ─────────────────────────────────────────────────

    def extract_subgraph(
        self, node_ids: List[str]
    ) -> Tuple[Dict[str, GraphNode], Dict[str, GraphEdge]]:
        """Extract subgraph containing only specified nodes and edges between them."""
        node_set = set(node_ids)
        sub_nodes = {
            nid: self._nodes[nid]
            for nid in node_ids
            if nid in self._nodes
        }
        sub_edges = {
            eid: edge
            for eid, edge in self._edges.items()
            if edge.source_id in node_set and edge.target_id in node_set
        }
        return sub_nodes, sub_edges

    # ── Supply Chain Analysis ────────────────────────────────────────────────

    def find_supply_chain(
        self, company_id: str, direction: str = "upstream", max_depth: int = 3
    ) -> List[List[GraphNode]]:
        """
        Find supply chain paths.

        direction: "upstream" (suppliers), "downstream" (customers)
        """
        if company_id not in self._nodes:
            return []

        supply_types = {
            EdgeType.SUPPLIER_OF, EdgeType.SUPPLY_CHAIN,
            EdgeType.DEPENDS_ON, EdgeType.PRODUCES,
        }

        chains: List[List[GraphNode]] = []
        current = [company_id]
        chains.append([self._nodes[company_id]])

        for _ in range(max_depth):
            next_level = []
            next_chains = []

            for chain_idx, node_id in enumerate(current):
                if direction == "upstream":
                    # Find suppliers (incoming edges)
                    neighbors = self.get_neighbors(node_id, supply_types, "incoming")
                else:
                    # Find customers (outgoing edges)
                    neighbors = self.get_neighbors(node_id, supply_types, "outgoing")

                for neighbor_node, _ in neighbors:
                    if neighbor_node.node_id not in [
                        n.node_id for chain in chains for n in chain
                    ]:
                        next_level.append(neighbor_node.node_id)
                        new_chain = chains[chain_idx].copy() if chain_idx < len(chains) else []
                        new_chain.append(neighbor_node)
                        next_chains.append(new_chain)

            if not next_level:
                break

            current = next_level
            chains = next_chains

        return chains

    # ── Query Methods ────────────────────────────────────────────────────────

    def query(self, query: GraphQuery) -> List[Tuple[GraphNode, int]]:
        """Execute a graph query."""
        if not query.start_node:
            return []

        start_id = self._name_index.get(query.start_node.lower(), query.start_node)
        if start_id not in self._nodes:
            return []

        bfs_result = self.bfs(start_id, query.max_depth, query.edge_types, query.direction)
        results: List[Tuple[GraphNode, int]] = []
        for depth, node_ids in bfs_result.items():
            if depth == 0:
                continue
            for nid in node_ids:
                node = self._nodes.get(nid)
                if node:
                    if query.node_types and node.node_type not in query.node_types:
                        continue
                    results.append((node, depth))

        return results[: query.limit]

    # ── Stats ────────────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        type_counts = defaultdict(int)
        for node in self._nodes.values():
            type_counts[node.node_type.value] += 1

        edge_type_counts = defaultdict(int)
        for edge in self._edges.values():
            edge_type_counts[edge.edge_type.value] += 1

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "node_types": dict(type_counts),
            "edge_types": dict(edge_type_counts),
            "density": (
                self.edge_count / (self.node_count * (self.node_count - 1))
                if self.node_count > 1
                else 0.0
            ),
        }

    def clear(self) -> None:
        """Clear the entire graph."""
        self._nodes.clear()
        self._edges.clear()
        self._adj_out.clear()
        self._adj_in.clear()
        self._name_index.clear()
