"""
Policy Dependency — dependency management between policy versions.

Policies can depend on other policies:
  - REQUIRES: Policy A REQUIRES Policy B (B must be active)
  - CONFLICTS_WITH: Policy A CONFLICTS_WITH Policy B (both cannot be active)
  - EXTENDS: Policy A EXTENDS Policy B (A inherits B's rules)
  - SUPERSEDES: Policy A SUPERSEDES Policy B (A replaces B)
  - REFERENCES: Policy A REFERENCES Policy B (loose coupling)

The dependency graph enables:
  - Validating activation (all required deps must be active)
  - Detecting conflicts before activation
  - Resolving dependency chains
  - Impact analysis: "what breaks if I deactivate this?"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Dependency types
# ---------------------------------------------------------------------------

class DependencyType(Enum):
    """Types of relationships between policy versions."""

    REQUIRES = auto()        # A requires B to be active
    CONFLICTS_WITH = auto()  # A conflicts with B (mutually exclusive)
    EXTENDS = auto()         # A extends B (inherits rules)
    SUPERSEDES = auto()      # A supersedes B (replaces)
    REFERENCES = auto()      # A references B (loose coupling)
    COMPLEMENTS = auto()     # A complements B (designed to work together)
    BLOCKS = auto()          # A blocks B from activating
    DEPRECATES = auto()      # A deprecates B


# ---------------------------------------------------------------------------
# Dependency constraint
# ---------------------------------------------------------------------------

@dataclass
class PolicyDependency:
    """
    A directed dependency edge between two policy versions.

    Represents a relationship from source_policy to target_policy.
    """

    dependency_id: str = ""
    source_policy_id: str = ""      # The policy that declares the dependency
    source_version: str = ""        # Specific version, or "" for all versions
    target_policy_id: str = ""      # The policy being depended on
    target_version_constraint: str = ""  # Version constraint, e.g., ">=1.0.0"

    dependency_type: DependencyType = DependencyType.REQUIRES

    # Whether this dependency is mandatory or advisory
    mandatory: bool = True

    # Human-readable rationale
    reason: str = ""
    reference: str = ""

    # Whether this dependency is currently satisfied
    satisfied: bool = False
    satisfaction_detail: str = ""

    # Timing
    declared_at: float = field(default_factory=time.time)
    verified_at: Optional[float] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_required(self) -> bool:
        return (
            self.dependency_type == DependencyType.REQUIRES
            and self.mandatory
        )

    @property
    def is_conflict(self) -> bool:
        return self.dependency_type in (
            DependencyType.CONFLICTS_WITH,
            DependencyType.BLOCKS,
        )

    @property
    def is_soft(self) -> bool:
        """Soft dependency — satisfied if possible, but not required."""
        return self.dependency_type in (
            DependencyType.REFERENCES,
            DependencyType.COMPLEMENTS,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "source_policy_id": self.source_policy_id,
            "source_version": self.source_version,
            "target_policy_id": self.target_policy_id,
            "target_version_constraint": self.target_version_constraint,
            "dependency_type": self.dependency_type.name,
            "mandatory": self.mandatory,
            "reason": self.reason,
            "reference": self.reference,
            "satisfied": self.satisfied,
            "satisfaction_detail": self.satisfaction_detail,
            "declared_at": self.declared_at,
            "verified_at": self.verified_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyDependency":
        return cls(
            dependency_id=data.get("dependency_id", ""),
            source_policy_id=data.get("source_policy_id", ""),
            source_version=data.get("source_version", ""),
            target_policy_id=data.get("target_policy_id", ""),
            target_version_constraint=data.get("target_version_constraint", ""),
            dependency_type=DependencyType[
                data.get("dependency_type", "REQUIRES")
            ],
            mandatory=data.get("mandatory", True),
            reason=data.get("reason", ""),
            reference=data.get("reference", ""),
            satisfied=data.get("satisfied", False),
            satisfaction_detail=data.get("satisfaction_detail", ""),
            declared_at=data.get("declared_at", time.time()),
            verified_at=data.get("verified_at"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"PolicyDependency({self.source_policy_id} --[{self.dependency_type.name}]--> "
            f"{self.target_policy_id})"
        )


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

@dataclass
class DependencyGraph:
    """
    Directed graph of policy dependency relationships.

    Provides:
      - Topological ordering for activation
      - Cycle detection
      - Conflict detection
      - Impact analysis (what depends on what)
      - Resolution: can this activation proceed?

    Graph structure:
      - nodes: set of policy_ids
      - edges: PolicyDependency[source → target]
      - Forward index: source → {targets}
      - Reverse index: target → {sources}
    """

    dependencies: List[PolicyDependency] = field(default_factory=list)

    # Indexes (built on demand)
    _forward: Dict[str, List[PolicyDependency]] = field(default_factory=dict)
    _reverse: Dict[str, List[PolicyDependency]] = field(default_factory=dict)
    _indexed: bool = False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, dep: PolicyDependency) -> None:
        """Add a dependency edge."""
        self.dependencies.append(dep)
        self._indexed = False

    def remove(self, dependency_id: str) -> bool:
        """Remove a dependency by ID."""
        before = len(self.dependencies)
        self.dependencies = [
            d for d in self.dependencies
            if d.dependency_id != dependency_id
        ]
        if len(self.dependencies) < before:
            self._indexed = False
            return True
        return False

    def clear(self) -> None:
        self.dependencies.clear()
        self._forward.clear()
        self._reverse.clear()
        self._indexed = False

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _ensure_indexed(self) -> None:
        """Build forward and reverse indexes."""
        if self._indexed:
            return

        self._forward.clear()
        self._reverse.clear()

        for dep in self.dependencies:
            # Forward: source → target
            if dep.source_policy_id not in self._forward:
                self._forward[dep.source_policy_id] = []
            self._forward[dep.source_policy_id].append(dep)

            # Reverse: target → source
            if dep.target_policy_id not in self._reverse:
                self._reverse[dep.target_policy_id] = []
            self._reverse[dep.target_policy_id].append(dep)

        self._indexed = True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_dependencies(
        self,
        policy_id: str,
        dep_type: Optional[DependencyType] = None,
    ) -> List[PolicyDependency]:
        """Get all dependencies declared by a policy (outgoing edges)."""
        self._ensure_indexed()
        deps = self._forward.get(policy_id, [])
        if dep_type:
            return [d for d in deps if d.dependency_type == dep_type]
        return list(deps)

    def get_dependents(
        self,
        policy_id: str,
        dep_type: Optional[DependencyType] = None,
    ) -> List[PolicyDependency]:
        """Get all policies that depend on this one (incoming edges)."""
        self._ensure_indexed()
        deps = self._reverse.get(policy_id, [])
        if dep_type:
            return [d for d in deps if d.dependency_type == dep_type]
        return list(deps)

    def get_required_dependencies(self, policy_id: str) -> List[PolicyDependency]:
        """Get REQUIRES dependencies (must be satisfied before activation)."""
        return self.get_dependencies(policy_id, DependencyType.REQUIRES)

    def get_conflicts(self, policy_id: str) -> List[PolicyDependency]:
        """Get CONFLICTS_WITH / BLOCKS dependencies."""
        deps = []
        deps.extend(self.get_dependencies(policy_id, DependencyType.CONFLICTS_WITH))
        deps.extend(self.get_dependencies(policy_id, DependencyType.BLOCKS))
        return deps

    def transitive_dependencies(
        self,
        policy_id: str,
        dep_type: Optional[DependencyType] = None,
    ) -> Set[str]:
        """Get all transitive dependencies (closure of outgoing REQUIRES)."""
        self._ensure_indexed()
        visited: Set[str] = set()
        stack = [policy_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            for dep in self.get_dependencies(current):
                if dep_type and dep.dependency_type != dep_type:
                    continue
                if dep.target_policy_id not in visited:
                    stack.append(dep.target_policy_id)

        visited.discard(policy_id)  # Don't include self
        return visited

    def transitive_dependents(self, policy_id: str) -> Set[str]:
        """Get all policies that transitively depend on this one."""
        self._ensure_indexed()
        visited: Set[str] = set()
        stack = [policy_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            for dep in self.get_dependents(current):
                if dep.source_policy_id not in visited:
                    stack.append(dep.source_policy_id)

        visited.discard(policy_id)
        return visited

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def has_cycle(self) -> bool:
        """Check if the dependency graph contains a cycle."""
        self._ensure_indexed()
        visited: Set[str] = set()
        in_stack: Set[str] = set()

        all_nodes = set(self._forward.keys()) | set(self._reverse.keys())

        def dfs(node: str) -> bool:
            visited.add(node)
            in_stack.add(node)
            for dep in self._forward.get(node, []):
                neighbor = dep.target_policy_id
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in in_stack:
                    return True
            in_stack.discard(node)
            return False

        for node in all_nodes:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the dependency graph."""
        self._ensure_indexed()
        all_nodes = set(self._forward.keys()) | set(self._reverse.keys())
        cycles: List[List[str]] = []
        visited: Set[str] = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            path.append(node)
            for dep in self._forward.get(node, []):
                neighbor = dep.target_policy_id
                if neighbor in path:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:])
                elif neighbor not in visited:
                    dfs(neighbor, path[:])
            path.pop()

        for node in all_nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    # ------------------------------------------------------------------
    # Activation validation
    # ------------------------------------------------------------------

    def validate_activation(
        self,
        policy_id: str,
        active_policy_ids: Set[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check if a policy can be activated given the current active set.

        Returns:
            (can_activate, reasons) — list of blocking reasons if not.
        """
        reasons: List[str] = []

        # Check REQUIRES: all required deps must be active
        for dep in self.get_required_dependencies(policy_id):
            if not dep.mandatory:
                continue
            if dep.target_policy_id not in active_policy_ids:
                reasons.append(
                    f"REQUIRES '{dep.target_policy_id}' (not active): {dep.reason}"
                )

        # Check CONFLICTS: no conflicting policy can be active
        for dep in self.get_conflicts(policy_id):
            if dep.target_policy_id in active_policy_ids:
                reasons.append(
                    f"CONFLICTS with '{dep.target_policy_id}' (currently active): {dep.reason}"
                )

        # Check reverse conflicts: no other policy has CONFLICTS with us while active
        for dep in self.get_dependents(policy_id, DependencyType.CONFLICTS_WITH):
            if dep.source_policy_id in active_policy_ids:
                reasons.append(
                    f"'{dep.source_policy_id}' CONFLICTS with this policy: {dep.reason}"
                )

        # Check BLOCKS: no other policy blocks us
        for dep in self.get_dependents(policy_id, DependencyType.BLOCKS):
            if dep.source_policy_id in active_policy_ids:
                reasons.append(
                    f"'{dep.source_policy_id}' BLOCKS this policy: {dep.reason}"
                )

        # Cycle check
        if self.has_cycle():
            cycles = self.find_cycles()
            for cycle in cycles:
                if policy_id in cycle:
                    reasons.append(
                        f"Cycle detected involving this policy: {' → '.join(cycle)}"
                    )

        return (len(reasons) == 0, reasons)

    def validate_deactivation(
        self,
        policy_id: str,
        active_policy_ids: Set[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check if a policy can be safely deactivated.

        Returns:
            (can_deactivate, reasons) — what depends on this policy?
        """
        reasons: List[str] = []

        # Check reverse REQUIRES: who requires us?
        for dep in self.get_dependents(policy_id, DependencyType.REQUIRES):
            if dep.source_policy_id in active_policy_ids:
                reasons.append(
                    f"'{dep.source_policy_id}' REQUIRES this policy: {dep.reason}"
                )

        return (len(reasons) == 0, reasons)

    # ------------------------------------------------------------------
    # Impact analysis
    # ------------------------------------------------------------------

    def activation_impact(self, policy_id: str) -> Dict[str, Any]:
        """What would be affected if this policy were activated?"""
        conflicts = self.get_conflicts(policy_id)
        required = self.get_required_dependencies(policy_id)
        blocked_by = self.get_dependents(policy_id, DependencyType.BLOCKS)

        return {
            "policy_id": policy_id,
            "required_dependencies": [
                {"policy": d.target_policy_id, "reason": d.reason}
                for d in required
            ],
            "conflicting_policies": [
                {"policy": d.target_policy_id, "reason": d.reason}
                for d in conflicts
            ],
            "blocked_by": [
                {"policy": d.source_policy_id, "reason": d.reason}
                for d in blocked_by
            ],
            "dependents_count": len(
                self.transitive_dependents(policy_id)
            ),
            "dependencies_count": len(
                self.transitive_dependencies(policy_id)
            ),
        }

    def deactivation_impact(self, policy_id: str) -> Dict[str, Any]:
        """What would break if this policy were deactivated?"""
        dependents = [
            d.source_policy_id
            for d in self.get_dependents(policy_id, DependencyType.REQUIRES)
        ]

        return {
            "policy_id": policy_id,
            "affected_policies": list(set(dependents)),
            "affected_count": len(set(dependents)),
            "total_dependents": len(
                self.transitive_dependents(policy_id)
            ),
        }

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def topological_order(self) -> List[str]:
        """
        Return policies in dependency order (prerequisites first).

        Policies that depend on others appear after their dependencies.
        """
        self._ensure_indexed()
        all_nodes = set(self._forward.keys()) | set(self._reverse.keys())

        # Build adjacency and in-degree
        in_degree: Dict[str, int] = {n: 0 for n in all_nodes}
        adjacency: Dict[str, List[str]] = {n: [] for n in all_nodes}

        for dep in self.dependencies:
            if dep.dependency_type == DependencyType.REQUIRES:
                src = dep.source_policy_id
                tgt = dep.target_policy_id
                if tgt not in in_degree:
                    in_degree[tgt] = 0
                if src not in adjacency:
                    adjacency[src] = []
                adjacency[tgt].append(src)
                in_degree[src] = in_degree.get(src, 0) + 1

        # Kahn's algorithm
        result: List[str] = []
        queue = [n for n in all_nodes if in_degree.get(n, 0) == 0]

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dependencies": [d.to_dict() for d in self.dependencies],
            "node_count": len(
                set(self._forward.keys()) | set(self._reverse.keys())
            ),
            "edge_count": len(self.dependencies),
            "has_cycle": self.has_cycle(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DependencyGraph":
        graph = cls()
        for dd in data.get("dependencies", []):
            graph.add(PolicyDependency.from_dict(dd))
        return graph

    def __repr__(self) -> str:
        return (
            f"DependencyGraph(nodes={len(self._forward)}, edges={len(self.dependencies)})"
        )
