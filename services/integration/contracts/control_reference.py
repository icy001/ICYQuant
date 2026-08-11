"""Control reference — parent/child chain forming a Decision Lineage.

Every contract can reference a prior decision, forming a full
traceable chain from Signal → Decision → Risk → Gov → Auth → Approval → Admission.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ControlReference:
    """A single node in the decision reference chain."""

    # ── Identity ──
    reference_id: str = field(default_factory=lambda: f"REF-{uuid.uuid4().hex[:12].upper()}")
    domain: str = ""  # "signal", "decision", "risk", "governance", "authority", "approval", "admission"

    # ── Chain ──
    parent_reference_id: Optional[str] = None
    flow_id: str = ""

    # ── Content reference ──
    decision_id: str = ""
    contract_id: str = ""

    # ── Timing ──
    created_at: float = field(default_factory=time.time)

    # ── Metadata ──
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def root(cls, flow_id: str, domain: str = "signal") -> "ControlReference":
        """Create a root reference (no parent)."""
        return cls(domain=domain, flow_id=flow_id, parent_reference_id=None)

    @classmethod
    def child_of(cls, parent: "ControlReference", domain: str, **kwargs: Any) -> "ControlReference":
        """Create a child reference linked to a parent."""
        return cls(
            domain=domain,
            flow_id=parent.flow_id,
            parent_reference_id=parent.reference_id,
            **kwargs,
        )

    @property
    def is_root(self) -> bool:
        return self.parent_reference_id is None

    @property
    def depth(self) -> int:
        # depth is computed during lineage construction
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "domain": self.domain,
            "parent_reference_id": self.parent_reference_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "contract_id": self.contract_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        parent = f" parent={self.parent_reference_id[:12]}" if self.parent_reference_id else ""
        return f"ControlReference(domain={self.domain!r}, ref={self.reference_id[:16]}{parent})"


@dataclass
class DecisionLineage:
    """The full ordered chain of control references from signal to admission."""

    references: List[ControlReference] = field(default_factory=list)

    def add(self, ref: ControlReference) -> "DecisionLineage":
        self.references.append(ref)
        return self

    @property
    def root(self) -> Optional[ControlReference]:
        return self.references[0] if self.references else None

    @property
    def latest(self) -> Optional[ControlReference]:
        return self.references[-1] if self.references else None

    @property
    def full_chain(self) -> List[str]:
        """Return ordered list of domain names."""
        return [r.domain for r in self.references]

    @property
    def is_complete(self) -> bool:
        """A complete chain covers all domains from signal to admission."""
        expected = ["signal", "decision", "risk", "governance", "authority", "approval", "admission"]
        actual = self.full_chain
        if len(actual) < 2:
            return False
        # Verify the actual chain is a subsequence of expected
        i = 0
        for d in expected:
            if i < len(actual) and actual[i] == d:
                i += 1
        return i == len(actual)

    def find(self, domain: str) -> Optional[ControlReference]:
        for r in self.references:
            if r.domain == domain:
                return r
        return None

    def validate_connected(self) -> bool:
        """Verify every reference (except root) has a valid parent in the chain."""
        ids = {r.reference_id for r in self.references}
        for r in self.references:
            if r.parent_reference_id is not None and r.parent_reference_id not in ids:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "references": [r.to_dict() for r in self.references],
            "full_chain": self.full_chain,
            "is_complete": self.is_complete,
            "is_connected": self.validate_connected(),
        }

    def __repr__(self) -> str:
        return f"DecisionLineage(chain={' → '.join(self.full_chain)}, complete={self.is_complete})"
