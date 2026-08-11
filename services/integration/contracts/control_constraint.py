"""Control constraint — every domain produces constraints, and the integration layer intersects them.

Key design:
  - Constraints carry provenance (source domain, policy version, rule ID).
  - intersect_constraints() takes the strictest: min for numeric, intersection for sets.
  - Conflicting allow/deny rules produce BLOCK.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from .contract_errors import ConstraintConflictError


class ConstraintType(Enum):
    """The kind of limit a constraint imposes."""

    MAX_NOTIONAL = auto()
    MAX_QUANTITY = auto()
    MAX_LEVERAGE = auto()
    MAX_EXPOSURE = auto()
    ALLOWED_SYMBOLS = auto()
    ALLOWED_SIDES = auto()
    ALLOWED_VENUES = auto()
    ALLOWED_ORDER_TYPES = auto()
    EXPIRY = auto()

    @property
    def label(self) -> str:
        _labels = {
            ConstraintType.MAX_NOTIONAL: "MAX_NOTIONAL",
            ConstraintType.MAX_QUANTITY: "MAX_QUANTITY",
            ConstraintType.MAX_LEVERAGE: "MAX_LEVERAGE",
            ConstraintType.MAX_EXPOSURE: "MAX_EXPOSURE",
            ConstraintType.ALLOWED_SYMBOLS: "ALLOWED_SYMBOLS",
            ConstraintType.ALLOWED_SIDES: "ALLOWED_SIDES",
            ConstraintType.ALLOWED_VENUES: "ALLOWED_VENUES",
            ConstraintType.ALLOWED_ORDER_TYPES: "ALLOWED_ORDER_TYPES",
            ConstraintType.EXPIRY: "EXPIRY",
        }
        return _labels.get(self, "UNKNOWN")


class ConstraintSource(Enum):
    """Which domain produced this constraint."""

    RISK = auto()
    GOVERNANCE = auto()
    AUTHORITY = auto()
    APPROVAL = auto()
    ADMISSION = auto()

    @property
    def label(self) -> str:
        _labels = {
            ConstraintSource.RISK: "RISK",
            ConstraintSource.GOVERNANCE: "GOVERNANCE",
            ConstraintSource.AUTHORITY: "AUTHORITY",
            ConstraintSource.APPROVAL: "APPROVAL",
            ConstraintSource.ADMISSION: "ADMISSION",
        }
        return _labels.get(self, "UNKNOWN")


class ConstraintRule(Enum):
    """The semantics of a constraint: numeric min/max, or set allow/deny."""

    MAX = auto()       # numeric: take min across sources
    MIN = auto()       # numeric: take max across sources (rare)
    ALLOW = auto()     # set: take intersection across sources
    DENY = auto()      # set: take union across sources (highest priority)
    EXACT = auto()     # must match exactly across sources


@dataclass
class ControlConstraint:
    """A single constraint produced by a domain gate, with full provenance."""

    # ── Identity ──
    constraint_id: str = ""
    constraint_type: ConstraintType = ConstraintType.MAX_NOTIONAL
    rule: ConstraintRule = ConstraintRule.MAX

    # ── Value ──
    numeric_value: Optional[float] = None
    set_value: Optional[Set[str]] = None

    # ── Provenance (who set this constraint and why) ──
    source: ConstraintSource = ConstraintSource.RISK
    policy_version: str = ""
    rule_id: str = ""
    reason: str = ""

    # ── Timing ──
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    # ── Constructors ──

    @classmethod
    def max_notional(
        cls,
        value: float,
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
        expires_at: Optional[float] = None,
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.MAX_NOTIONAL,
            rule=ConstraintRule.MAX,
            numeric_value=value,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
            expires_at=expires_at,
        )

    @classmethod
    def max_quantity(
        cls,
        value: float,
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
        expires_at: Optional[float] = None,
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.MAX_QUANTITY,
            rule=ConstraintRule.MAX,
            numeric_value=value,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
            expires_at=expires_at,
        )

    @classmethod
    def max_leverage(
        cls,
        value: float,
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
        expires_at: Optional[float] = None,
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.MAX_LEVERAGE,
            rule=ConstraintRule.MAX,
            numeric_value=value,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
            expires_at=expires_at,
        )

    @classmethod
    def max_exposure(
        cls,
        value: float,
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
        expires_at: Optional[float] = None,
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.MAX_EXPOSURE,
            rule=ConstraintRule.MAX,
            numeric_value=value,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
            expires_at=expires_at,
        )

    @classmethod
    def allowed_symbols(
        cls,
        values: Set[str],
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.ALLOWED_SYMBOLS,
            rule=ConstraintRule.ALLOW,
            set_value=values,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
        )

    @classmethod
    def allowed_sides(
        cls,
        values: Set[str],
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.ALLOWED_SIDES,
            rule=ConstraintRule.ALLOW,
            set_value=values,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
        )

    @classmethod
    def allowed_venues(
        cls,
        values: Set[str],
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.ALLOWED_VENUES,
            rule=ConstraintRule.ALLOW,
            set_value=values,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
        )

    @classmethod
    def allowed_order_types(
        cls,
        values: Set[str],
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.ALLOWED_ORDER_TYPES,
            rule=ConstraintRule.ALLOW,
            set_value=values,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
        )

    @classmethod
    def deny_symbols(
        cls,
        values: Set[str],
        source: ConstraintSource,
        policy_version: str = "",
        rule_id: str = "",
        reason: str = "",
    ) -> "ControlConstraint":
        return cls(
            constraint_type=ConstraintType.ALLOWED_SYMBOLS,
            rule=ConstraintRule.DENY,
            set_value=values,
            source=source,
            policy_version=policy_version,
            rule_id=rule_id,
            reason=reason,
        )

    # ── Properties ──

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def value_repr(self) -> str:
        if self.numeric_value is not None:
            return str(self.numeric_value)
        if self.set_value is not None:
            return str(sorted(self.set_value))
        return "<empty>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_type": self.constraint_type.name,
            "rule": self.rule.name,
            "numeric_value": self.numeric_value,
            "set_value": sorted(self.set_value) if self.set_value else None,
            "source": self.source.name,
            "policy_version": self.policy_version,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    def __repr__(self) -> str:
        return (
            f"ControlConstraint(type={self.constraint_type.name}, "
            f"rule={self.rule.name}, source={self.source.name}, "
            f"value={self.value_repr})"
        )


@dataclass
class EffectiveConstraints:
    """The resolved intersection of all constraints from all domains.

    Rules:
      - MAX rule: take min across all sources
      - ALLOW rule: take intersection across all sources
      - DENY rule: take union across all sources (denies override allows)
    """

    constraints: List[ControlConstraint] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)

    def get(self, constraint_type: ConstraintType) -> Optional[ControlConstraint]:
        for c in self.constraints:
            if c.constraint_type == constraint_type:
                return c
        return None

    def get_numeric(self, constraint_type: ConstraintType) -> Optional[float]:
        c = self.get(constraint_type)
        if c:
            return c.numeric_value
        return None

    def get_set(self, constraint_type: ConstraintType) -> Optional[Set[str]]:
        c = self.get(constraint_type)
        if c:
            return c.set_value
        return None

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraints": [c.to_dict() for c in self.constraints],
            "conflicts": self.conflicts,
        }

    def __repr__(self) -> str:
        types = [c.constraint_type.name for c in self.constraints]
        conflict_note = f" conflicts={len(self.conflicts)}" if self.conflicts else ""
        return f"EffectiveConstraints({types}{conflict_note})"


# ── Constraint intersection logic ──


def intersect_constraints(
    constraints: List[ControlConstraint],
) -> EffectiveConstraints:
    """Compute effective constraints by intersecting all domain constraints.

    MAX rule: take the minimum numeric value (most restrictive).
    ALLOW rule: take the set intersection.
    DENY rule: take the set union (denies are always preserved).

    Raises ConstraintConflictError if allow/deny within same type produces
    an empty intersection.
    """
    if not constraints:
        return EffectiveConstraints()

    # Group by (constraint_type, rule)
    by_type: Dict[ConstraintType, Dict[str, List[ControlConstraint]]] = {}

    for c in constraints:
        ct = c.constraint_type
        if ct not in by_type:
            by_type[ct] = {}
        rule_key = c.rule.name
        if rule_key not in by_type[ct]:
            by_type[ct][rule_key] = []
        by_type[ct][rule_key].append(c)

    effective: List[ControlConstraint] = []
    conflicts: List[str] = []

    for ct, by_rule in by_type.items():
        # ── Process DENY rules first (highest priority) ──
        deny_constraints = by_rule.get("DENY", [])
        deny_union: Set[str] = set()
        deny_sources: List[str] = []
        for c in deny_constraints:
            if c.set_value:
                deny_union |= c.set_value
            deny_sources.append(c.source.name)

        # ── Process MAX rules: take minimum ──
        max_constraints = by_rule.get("MAX", [])
        if max_constraints:
            numeric_values = [
                c.numeric_value for c in max_constraints if c.numeric_value is not None
            ]
            if numeric_values:
                min_value = min(numeric_values)
                tightest = min(max_constraints, key=lambda c: c.numeric_value or float("inf"))
                effective.append(ControlConstraint(
                    constraint_type=ct,
                    rule=ConstraintRule.MAX,
                    numeric_value=min_value,
                    source=tightest.source,
                    policy_version=tightest.policy_version,
                    rule_id=tightest.rule_id,
                    reason=f"Intersection of {len(max_constraints)} MAX constraints: "
                           f"min={min_value}",
                ))

        # ── Process ALLOW rules: take intersection ──
        allow_constraints = by_rule.get("ALLOW", [])
        if allow_constraints:
            allow_sets = [c.set_value for c in allow_constraints if c.set_value is not None]
            if allow_sets:
                intersection = allow_sets[0].copy()
                for s in allow_sets[1:]:
                    intersection &= s

                # Remove denied items
                if deny_union:
                    before = len(intersection)
                    intersection -= deny_union
                    removed = before - len(intersection)
                    if removed > 0:
                        conflicts.append(
                            f"DENY removed {removed} item(s) from ALLOW set for {ct.name}: "
                            f"deny sources={deny_sources}"
                        )

                if not intersection:
                    raise ConstraintConflictError(
                        message=f"Constraint conflict for {ct.name}: "
                                f"allow intersection is empty after deny removal",
                        constraint_a=f"ALLOW({[c.source.name for c in allow_constraints]})",
                        constraint_b=f"DENY({deny_sources})",
                    )

                effective.append(ControlConstraint(
                    constraint_type=ct,
                    rule=ConstraintRule.ALLOW,
                    set_value=intersection,
                    source=allow_constraints[0].source,
                    policy_version=allow_constraints[0].policy_version,
                    rule_id=allow_constraints[0].rule_id,
                    reason=f"Intersection of {len(allow_constraints)} ALLOW sets = "
                           f"{len(intersection)} items",
                ))

        # ── If only DENY rules exist (no ALLOW) ──
        if deny_constraints and not allow_constraints:
            conflicts.append(
                f"DENY-only constraint for {ct.name} from {deny_sources} — "
                f"items {sorted(deny_union)} are blocked"
            )

    return EffectiveConstraints(constraints=effective, conflicts=conflicts)
