"""
Policy Trace — detailed trace of policy version evaluation.

Records every step of a policy evaluation for full auditability and debugging:
  - Which policy versions were considered
  - Evaluation order and priority
  - Per-rule results with before/after snapshots
  - Timing breakdown
  - Effect chain
  - Decision path (why was this decision made?)

This enables:
  - Full audit trails for regulatory compliance
  - Debugging "why was my order blocked?"
  - Performance profiling of policy evaluation
  - Impact analysis of policy changes
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy_effect import EffectType, PolicyEffect
from .policy_priority import PolicyPriorityLevel
from .policy_status import PolicyLifecycleStatus


# ---------------------------------------------------------------------------
# Trace node types
# ---------------------------------------------------------------------------

@dataclass
class TraceNode:
    """
    A single node in the policy evaluation trace tree.

    Represents one evaluation step: a policy version, a rule set, a rule,
    a condition, or an effect application.
    """

    node_id: str = field(default_factory=lambda: f"TN-{uuid.uuid4().hex[:8]}")
    node_type: str = ""  # POLICY, RULE_SET, RULE, CONDITION, EFFECT, EVALUATION

    # Target
    target_id: str = ""   # policy_id, rule_set_id, rule_id, etc.
    target_name: str = ""
    target_version: str = ""

    # Result
    passed: bool = True
    result_summary: str = ""
    result_detail: Dict[str, Any] = field(default_factory=dict)

    # Priority
    priority: Optional[PolicyPriorityLevel] = None

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0

    # Children (nested evaluations)
    children: List["TraceNode"] = field(default_factory=list)

    # Effects generated at this node
    effects: List[PolicyEffect] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Tree management
    # ------------------------------------------------------------------

    def add_child(self, child: "TraceNode") -> "TraceNode":
        self.children.append(child)
        return self

    def find(self, target_id: str) -> Optional["TraceNode"]:
        """Find a node by target_id (recursive)."""
        if self.target_id == target_id:
            return self
        for child in self.children:
            found = child.find(target_id)
            if found is not None:
                return found
        return None

    def flatten(self) -> List["TraceNode"]:
        """Return self + all descendants as a flat list."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def count_by_type(self, node_type: str) -> int:
        return sum(1 for n in self.flatten() if n.node_type == node_type)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth for c in self.children)

    def all_failed(self) -> List["TraceNode"]:
        """Return all nodes that failed evaluation."""
        return [n for n in self.flatten() if not n.passed]

    def all_passed(self) -> List["TraceNode"]:
        """Return all nodes that passed evaluation."""
        return [n for n in self.flatten() if n.passed]

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def finish(self) -> "TraceNode":
        """Mark evaluation as complete."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        return self

    def total_duration_ms(self) -> float:
        """Cumulative duration including all children."""
        total = self.duration_ms
        for child in self.children:
            total += child.total_duration_ms()
        return total

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "target_version": self.target_version,
            "passed": self.passed,
            "result_summary": self.result_summary,
            "result_detail": self.result_detail,
            "priority": self.priority.name if self.priority else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "children": [c.to_dict() for c in self.children],
            "effects": [e.to_dict() for e in self.effects],
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceNode":
        node = cls(
            node_id=data.get("node_id", ""),
            node_type=data.get("node_type", ""),
            target_id=data.get("target_id", ""),
            target_name=data.get("target_name", ""),
            target_version=data.get("target_version", ""),
            passed=data.get("passed", True),
            result_summary=data.get("result_summary", ""),
            result_detail=data.get("result_detail", {}),
            priority=(
                PolicyPriorityLevel[data["priority"]]
                if data.get("priority")
                else None
            ),
            start_time=data.get("start_time", time.time()),
            end_time=data.get("end_time"),
            duration_ms=data.get("duration_ms", 0.0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )
        for cd in data.get("children", []):
            node.add_child(cls.from_dict(cd))
        for ed in data.get("effects", []):
            node.effects.append(PolicyEffect.from_dict(ed))
        return node

    def __repr__(self) -> str:
        return (
            f"TraceNode({self.node_type}:{self.target_id}, "
            f"passed={self.passed}, children={len(self.children)})"
        )


# ---------------------------------------------------------------------------
# Evaluation trace
# ---------------------------------------------------------------------------

@dataclass
class EvaluationTrace:
    """
    Complete trace of a policy evaluation run.

    Captures the full evaluation tree with timing, decisions, and effects.
    Provides explainability: why exactly was this decision made?
    """

    trace_id: str = field(default_factory=lambda: f"TR-{uuid.uuid4().hex[:12]}")
    decision_id: str = ""
    request_id: str = ""

    # Root of the evaluation trace tree
    root: Optional[TraceNode] = None

    # Aggregate stats
    total_policies: int = 0
    total_rule_sets: int = 0
    total_rules: int = 0
    total_conditions: int = 0

    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    total_duration_ms: float = 0.0

    # Final verdict
    verdict: str = "ALLOW"  # ALLOW, REVIEW, BLOCK
    verdict_reason: str = ""

    # Explanation (built from trace)
    explanation: str = ""
    decision_path: List[str] = field(default_factory=list)

    # Version info
    evaluated_versions: List[Dict[str, str]] = field(default_factory=list)
    skipped_versions: List[Dict[str, str]] = field(default_factory=list)

    # Errors
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Trace building
    # ------------------------------------------------------------------

    def start(self) -> "EvaluationTrace":
        """Mark evaluation as started."""
        self.started_at = time.time()
        self.root = TraceNode(
            node_type="EVALUATION",
            target_id=self.decision_id,
            start_time=self.started_at,
        )
        return self

    def add_policy_node(
        self,
        policy_id: str,
        policy_name: str,
        version: str,
        priority: PolicyPriorityLevel,
        status: PolicyLifecycleStatus,
        skipped: bool = False,
        skip_reason: str = "",
    ) -> TraceNode:
        """Add a policy-level trace node."""
        if skipped:
            node = TraceNode(
                node_type="POLICY",
                target_id=policy_id,
                target_name=policy_name,
                target_version=version,
                priority=priority,
                passed=True,
                result_summary=f"Skipped: {skip_reason}",
            )
            self.skipped_versions.append({
                "policy_id": policy_id,
                "version": version,
                "reason": skip_reason,
            })
        else:
            node = TraceNode(
                node_type="POLICY",
                target_id=policy_id,
                target_name=policy_name,
                target_version=version,
                priority=priority,
            )
            self.evaluated_versions.append({
                "policy_id": policy_id,
                "version": version,
                "priority": priority.name,
                "status": status.name,
            })

        if self.root:
            self.root.add_child(node)
        return node

    def add_rule_set_node(
        self,
        parent: TraceNode,
        rule_set_id: str,
        rule_set_name: str,
        passed: bool,
    ) -> TraceNode:
        """Add a rule-set-level trace node."""
        node = TraceNode(
            node_type="RULE_SET",
            target_id=rule_set_id,
            target_name=rule_set_name,
            passed=passed,
        )
        parent.add_child(node)
        return node

    def add_rule_node(
        self,
        parent: TraceNode,
        rule_id: str,
        rule_name: str,
        passed: bool,
        metric: str = "",
        actual: Any = None,
        expected: str = "",
        detail: str = "",
    ) -> TraceNode:
        """Add a rule-level trace node."""
        node = TraceNode(
            node_type="RULE",
            target_id=rule_id,
            target_name=rule_name,
            passed=passed,
            result_summary=detail,
            result_detail={
                "metric": metric,
                "actual": actual,
                "expected": expected,
            },
        )
        parent.add_child(node)
        return node

    def add_effect_node(
        self,
        parent: TraceNode,
        effect: PolicyEffect,
    ) -> "EvaluationTrace":
        """Attach an effect to a trace node."""
        parent.effects.append(effect)
        return self

    def add_error(
        self,
        node: Optional[TraceNode],
        error: str,
        policy_id: str = "",
        version_id: str = "",
    ) -> None:
        """Record an evaluation error."""
        self.error_count += 1
        error_entry = {
            "policy_id": policy_id,
            "version_id": version_id,
            "error": error,
            "timestamp": time.time(),
        }
        self.errors.append(error_entry)
        if node:
            node.passed = False
            node.result_summary = f"ERROR: {error}"

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete(self, verdict: str = "", reason: str = "") -> "EvaluationTrace":
        """Mark evaluation as complete and compute stats."""
        self.completed_at = time.time()
        self.total_duration_ms = (
            (self.completed_at - self.started_at) * 1000
        )
        self.verdict = verdict or self.verdict
        self.verdict_reason = reason or self.verdict_reason

        if self.root:
            self.root.finish()
            self._compute_stats()
            self._build_explanation()

        return self

    def _compute_stats(self) -> None:
        """Compute aggregate statistics from the trace tree."""
        if not self.root:
            return

        all_nodes = self.root.flatten()
        self.total_policies = sum(
            1 for n in all_nodes if n.node_type == "POLICY"
        )
        self.total_rule_sets = sum(
            1 for n in all_nodes if n.node_type == "RULE_SET"
        )
        self.total_rules = sum(
            1 for n in all_nodes if n.node_type == "RULE"
        )
        self.total_conditions = sum(
            1 for n in all_nodes if n.node_type == "CONDITION"
        )

        self.passed_count = sum(1 for n in all_nodes if n.passed)
        self.failed_count = sum(1 for n in all_nodes if not n.passed)

    def _build_explanation(self) -> None:
        """Build a human-readable explanation from the trace."""
        if not self.root:
            return

        failed_nodes = self.root.all_failed()
        decision_path: List[str] = []

        decision_path.append(
            f"Evaluation of {self.total_policies} policy version(s) "
            f"({self.total_rule_sets} rule sets, {self.total_rules} rules)"
        )

        for node in self.root.children:
            if node.node_type == "POLICY":
                status = "PASS" if node.passed else "FAIL"
                decision_path.append(
                    f"  Policy '{node.target_name}' (v{node.target_version}) "
                    f": {status} — {node.result_summary}"
                )
                for child in node.children:
                    child_status = "✓" if child.passed else "✗"
                    decision_path.append(
                        f"    [{child_status}] {child.node_type} "
                        f"'{child.target_name}': {child.result_summary}"
                    )

        if self.verdict == "BLOCK":
            failed_policies = [
                f"'{n.target_name}'" for n in self.root.children
                if not n.passed and n.node_type == "POLICY"
            ]
            decision_path.append(
                f"\nDECISION: BLOCKED — Failed policies: {', '.join(failed_policies)}"
            )
        elif self.verdict == "REVIEW":
            decision_path.append("\nDECISION: REVIEW required")
        else:
            decision_path.append("\nDECISION: ALLOWED")

        self.decision_path = decision_path
        self.explanation = "\n".join(decision_path)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def blocked_policies(self) -> List[str]:
        """Return list of policy IDs that failed/blocked."""
        if not self.root:
            return []
        return [
            n.target_id
            for n in self.root.children
            if n.node_type == "POLICY" and not n.passed
        ]

    @property
    def failed_rules(self) -> List[Dict[str, Any]]:
        """Return details of all failed rules."""
        if not self.root:
            return []
        results = []
        for node in self.root.all_failed():
            if node.node_type == "RULE":
                results.append({
                    "rule_id": node.target_id,
                    "rule_name": node.target_name,
                    "reason": node.result_summary,
                    "detail": node.result_detail,
                })
        return results

    def get_policy_trace(self, policy_id: str) -> Optional[TraceNode]:
        """Get the trace node for a specific policy."""
        if not self.root:
            return None
        return self.root.find(policy_id)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "root": self.root.to_dict() if self.root else None,
            "total_policies": self.total_policies,
            "total_rule_sets": self.total_rule_sets,
            "total_rules": self.total_rules,
            "total_conditions": self.total_conditions,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "explanation": self.explanation,
            "decision_path": self.decision_path,
            "evaluated_versions": self.evaluated_versions,
            "skipped_versions": self.skipped_versions,
            "errors": self.errors,
            "has_failures": self.has_failures,
            "has_errors": self.has_errors,
            "blocked_policies": self.blocked_policies,
            "failed_rules": self.failed_rules,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationTrace":
        trace = cls(
            trace_id=data.get("trace_id", ""),
            decision_id=data.get("decision_id", ""),
            request_id=data.get("request_id", ""),
            total_policies=data.get("total_policies", 0),
            total_rule_sets=data.get("total_rule_sets", 0),
            total_rules=data.get("total_rules", 0),
            total_conditions=data.get("total_conditions", 0),
            passed_count=data.get("passed_count", 0),
            failed_count=data.get("failed_count", 0),
            skipped_count=data.get("skipped_count", 0),
            error_count=data.get("error_count", 0),
            started_at=data.get("started_at", time.time()),
            completed_at=data.get("completed_at"),
            total_duration_ms=data.get("total_duration_ms", 0.0),
            verdict=data.get("verdict", "ALLOW"),
            verdict_reason=data.get("verdict_reason", ""),
            explanation=data.get("explanation", ""),
            decision_path=data.get("decision_path", []),
            evaluated_versions=data.get("evaluated_versions", []),
            skipped_versions=data.get("skipped_versions", []),
            errors=data.get("errors", []),
            metadata=data.get("metadata", {}),
        )
        if data.get("root"):
            trace.root = TraceNode.from_dict(data["root"])
        return trace

    # ------------------------------------------------------------------
    # Print-friendly output
    # ------------------------------------------------------------------

    def print_tree(self) -> str:
        """Render the trace tree as indented ASCII text."""
        if not self.root:
            return "<empty trace>"
        return self._render_node(self.root, 0)

    @staticmethod
    def _render_node(node: TraceNode, indent: int) -> str:
        prefix = "  " * indent
        status = "PASS" if node.passed else "FAIL"
        lines = [
            f"{prefix}[{status}] {node.node_type}: "
            f"{node.target_name or node.target_id}"
        ]
        if node.result_summary:
            lines.append(f"{prefix}  | {node.result_summary}")
        if node.duration_ms > 0:
            lines.append(f"{prefix}  | {node.duration_ms:.2f}ms")
        for effect in node.effects:
            lines.append(f"{prefix}  EFFECT: {effect.display_string}")
        for child in node.children:
            lines.append(EvaluationTrace._render_node(child, indent + 1))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"EvaluationTrace({self.trace_id}, verdict={self.verdict}, "
            f"policies={self.total_policies}, "
            f"passed={self.passed_count}, failed={self.failed_count})"
        )


# ---------------------------------------------------------------------------
# Trace diff — compare two evaluation traces
# ---------------------------------------------------------------------------

@dataclass
class TraceDiff:
    """
    Compare two evaluation traces to identify what changed.

    Useful for:
      - Impact analysis: "How does the new policy version affect decisions?"
      - Regression detection: "Did the new version cause previously-passing checks to fail?"
    """

    trace_a: EvaluationTrace
    trace_b: EvaluationTrace

    # Diff results
    verdict_changed: bool = False
    new_policies: List[str] = field(default_factory=list)
    removed_policies: List[str] = field(default_factory=list)
    changed_outcomes: List[Dict[str, str]] = field(default_factory=list)
    new_failures: List[str] = field(default_factory=list)
    resolved_failures: List[str] = field(default_factory=list)
    timing_diff_ms: float = 0.0

    def __post_init__(self):
        self._compute_diff()

    def _compute_diff(self) -> None:
        """Compute diff between two traces."""
        a_policies = {
            v["policy_id"]: v for v in self.trace_a.evaluated_versions
        }
        b_policies = {
            v["policy_id"]: v for v in self.trace_b.evaluated_versions
        }

        # New/removed policies
        a_ids = set(a_policies.keys())
        b_ids = set(b_policies.keys())
        self.new_policies = sorted(b_ids - a_ids)
        self.removed_policies = sorted(a_ids - b_ids)

        # Changed outcomes
        for pid in a_ids & b_ids:
            a_failed = pid in self.trace_a.blocked_policies
            b_failed = pid in self.trace_b.blocked_policies
            if a_failed != b_failed:
                self.changed_outcomes.append({
                    "policy_id": pid,
                    "old": "BLOCKED" if a_failed else "ALLOWED",
                    "new": "BLOCKED" if b_failed else "ALLOWED",
                })
                if b_failed:
                    self.new_failures.append(pid)
                else:
                    self.resolved_failures.append(pid)

        # Verdict change
        self.verdict_changed = (
            self.trace_a.verdict != self.trace_b.verdict
        )

        # Timing diff
        self.timing_diff_ms = (
            self.trace_b.total_duration_ms - self.trace_a.total_duration_ms
        )

    @property
    def has_changes(self) -> bool:
        return (
            self.verdict_changed
            or bool(self.new_policies)
            or bool(self.removed_policies)
            or bool(self.changed_outcomes)
            or bool(self.new_failures)
            or bool(self.resolved_failures)
        )

    @property
    def impact_summary(self) -> str:
        """Human-readable summary of changes between two traces."""
        if not self.has_changes:
            return "No changes detected between evaluations."

        parts = []
        if self.verdict_changed:
            parts.append(
                f"Verdict changed: {self.trace_a.verdict} → {self.trace_b.verdict}"
            )
        if self.new_policies:
            parts.append(f"New policies: {self.new_policies}")
        if self.removed_policies:
            parts.append(f"Removed policies: {self.removed_policies}")
        if self.new_failures:
            parts.append(f"New failures: {self.new_failures}")
        if self.resolved_failures:
            parts.append(f"Resolved failures: {self.resolved_failures}")
        if self.timing_diff_ms != 0:
            direction = "slower" if self.timing_diff_ms > 0 else "faster"
            parts.append(
                f"Timing: {abs(self.timing_diff_ms):.2f}ms {direction}"
            )

        return "; ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_changed": self.verdict_changed,
            "old_verdict": self.trace_a.verdict,
            "new_verdict": self.trace_b.verdict,
            "new_policies": self.new_policies,
            "removed_policies": self.removed_policies,
            "changed_outcomes": self.changed_outcomes,
            "new_failures": self.new_failures,
            "resolved_failures": self.resolved_failures,
            "timing_diff_ms": self.timing_diff_ms,
            "has_changes": self.has_changes,
            "impact_summary": self.impact_summary,
        }
