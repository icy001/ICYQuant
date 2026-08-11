"""
Policy Effect — structured outcomes of policy evaluation.

Defines what happens when a policy is evaluated: effects can be
multiple and cumulative, ranging from informational logging to
hard execution blocks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Effect types
# ---------------------------------------------------------------------------

class EffectType(Enum):
    """
    Types of policy evaluation effects.

    Arranged from most permissive to most restrictive.
    """

    # Permissive
    ALLOW = auto()           # Explicitly allow the decision
    LOG = auto()             # Log / record only
    NOTIFY = auto()          # Send notification

    # Advisory
    INFO = auto()            # Informational message
    WARNING = auto()         # Warning — no blocking
    RECOMMENDATION = auto()  # Recommended action (not mandatory)

    # Restrictive
    FLAG = auto()            # Flag for review
    REDUCE_SCOPE = auto()    # Reduce decision scope (e.g., smaller allocation)
    REQUIRE_APPROVAL = auto()  # Require manual approval
    FREEZE_POSITION = auto()   # Freeze specific positions
    FREEZE_NEW = auto()        # Freeze new activity

    # Blocking
    BLOCK = auto()           # Block the decision
    SUSPEND = auto()         # Suspend the decision-making process
    EMERGENCY_EXIT = auto()  # Emergency shutdown / exit all positions

    @property
    def is_blocking(self) -> bool:
        return self in (
            EffectType.BLOCK,
            EffectType.SUSPEND,
            EffectType.EMERGENCY_EXIT,
        )

    @property
    def requires_review(self) -> bool:
        return self in (
            EffectType.FLAG,
            EffectType.REQUIRE_APPROVAL,
            EffectType.REDUCE_SCOPE,
        )

    @property
    def is_advisory(self) -> bool:
        return self in (
            EffectType.INFO,
            EffectType.WARNING,
            EffectType.RECOMMENDATION,
        )

    @property
    def is_permissive(self) -> bool:
        return self in (
            EffectType.ALLOW,
            EffectType.LOG,
            EffectType.NOTIFY,
        )


class EffectSeverity(Enum):
    """How severe the effect is — used for aggregation."""

    NONE = 0
    LOW = 10
    MEDIUM = 30
    HIGH = 50
    CRITICAL = 80
    BLOCKING = 100

    @classmethod
    def for_effect_type(cls, effect_type: EffectType) -> "EffectSeverity":
        mapping = {
            EffectType.ALLOW: cls.NONE,
            EffectType.LOG: cls.LOW,
            EffectType.NOTIFY: cls.LOW,
            EffectType.INFO: cls.LOW,
            EffectType.WARNING: cls.MEDIUM,
            EffectType.RECOMMENDATION: cls.MEDIUM,
            EffectType.FLAG: cls.HIGH,
            EffectType.REDUCE_SCOPE: cls.HIGH,
            EffectType.REQUIRE_APPROVAL: cls.HIGH,
            EffectType.FREEZE_POSITION: cls.CRITICAL,
            EffectType.FREEZE_NEW: cls.CRITICAL,
            EffectType.BLOCK: cls.BLOCKING,
            EffectType.SUSPEND: cls.BLOCKING,
            EffectType.EMERGENCY_EXIT: cls.BLOCKING,
        }
        return mapping.get(effect_type, cls.MEDIUM)


# ---------------------------------------------------------------------------
# Policy Effect
# ---------------------------------------------------------------------------

@dataclass
class PolicyEffect:
    """
    A single structured outcome from policy evaluation.

    Each effect records:
      - What happened (effect_type)
      - Why it happened (reason, rule references)
      - What to do about it (action, parameters)
      - When it happened and who caused it
    """

    effect_id: str = ""
    effect_type: EffectType = EffectType.INFO
    severity: EffectSeverity = EffectSeverity.MEDIUM

    # Source
    source_policy_id: str = ""
    source_version_id: str = ""
    source_rule_id: str = ""
    source_rule_set_id: str = ""

    # Content
    reason: str = ""
    message: str = ""
    action: str = ""              # Recommended or required action
    action_params: Dict[str, Any] = field(default_factory=dict)

    # Context
    metric: str = ""
    actual_value: Any = None
    expected_value: str = ""

    # Timing
    timestamp: float = field(default_factory=time.time)

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.severity == EffectSeverity.MEDIUM:
            self.severity = EffectSeverity.for_effect_type(self.effect_type)

    @property
    def is_blocking(self) -> bool:
        return self.effect_type.is_blocking

    @property
    def requires_review(self) -> bool:
        return self.effect_type.requires_review

    @property
    def is_advisory(self) -> bool:
        return self.effect_type.is_advisory

    @property
    def display_string(self) -> str:
        parts = [f"[{self.effect_type.name}]"]
        if self.message:
            parts.append(self.message)
        elif self.reason:
            parts.append(self.reason)
        if self.metric:
            parts.append(f"({self.metric}: {self.actual_value})")
        return " ".join(parts)

    # ---- Factory methods ----

    @classmethod
    def allow(
        cls, source_policy_id: str = "", reason: str = "", **kwargs
    ) -> "PolicyEffect":
        return cls(
            effect_type=EffectType.ALLOW,
            severity=EffectSeverity.NONE,
            source_policy_id=source_policy_id,
            reason=reason or "Decision explicitly allowed",
            **kwargs,
        )

    @classmethod
    def warn(
        cls, source_policy_id: str = "", source_rule_id: str = "",
        metric: str = "", actual: Any = None, expected: str = "",
        message: str = "", **kwargs,
    ) -> "PolicyEffect":
        return cls(
            effect_type=EffectType.WARNING,
            severity=EffectSeverity.MEDIUM,
            source_policy_id=source_policy_id,
            source_rule_id=source_rule_id,
            metric=metric,
            actual_value=actual,
            expected_value=expected,
            message=message or f"Policy warning: {metric}",
            **kwargs,
        )

    @classmethod
    def block(
        cls, source_policy_id: str = "", source_rule_id: str = "",
        metric: str = "", actual: Any = None, expected: str = "",
        reason: str = "", **kwargs,
    ) -> "PolicyEffect":
        return cls(
            effect_type=EffectType.BLOCK,
            severity=EffectSeverity.BLOCKING,
            source_policy_id=source_policy_id,
            source_rule_id=source_rule_id,
            metric=metric,
            actual_value=actual,
            expected_value=expected,
            reason=reason or f"Decision blocked: {metric}",
            **kwargs,
        )

    @classmethod
    def require_approval(
        cls, source_policy_id: str = "", reason: str = "", **kwargs,
    ) -> "PolicyEffect":
        return cls(
            effect_type=EffectType.REQUIRE_APPROVAL,
            severity=EffectSeverity.HIGH,
            source_policy_id=source_policy_id,
            reason=reason or "Approval required",
            **kwargs,
        )

    @classmethod
    def emergency_exit(
        cls, source_policy_id: str = "", reason: str = "", **kwargs,
    ) -> "PolicyEffect":
        return cls(
            effect_type=EffectType.EMERGENCY_EXIT,
            severity=EffectSeverity.BLOCKING,
            source_policy_id=source_policy_id,
            reason=reason or "Emergency exit triggered",
            **kwargs,
        )

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "effect_type": self.effect_type.name,
            "severity": self.severity.name,
            "source_policy_id": self.source_policy_id,
            "source_version_id": self.source_version_id,
            "source_rule_id": self.source_rule_id,
            "source_rule_set_id": self.source_rule_set_id,
            "reason": self.reason,
            "message": self.message,
            "action": self.action,
            "action_params": self.action_params,
            "metric": self.metric,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyEffect":
        return cls(
            effect_id=data.get("effect_id", ""),
            effect_type=EffectType[data.get("effect_type", "INFO")],
            severity=EffectSeverity[data.get("severity", "MEDIUM")],
            source_policy_id=data.get("source_policy_id", ""),
            source_version_id=data.get("source_version_id", ""),
            source_rule_id=data.get("source_rule_id", ""),
            source_rule_set_id=data.get("source_rule_set_id", ""),
            reason=data.get("reason", ""),
            message=data.get("message", ""),
            action=data.get("action", ""),
            action_params=data.get("action_params", {}),
            metric=data.get("metric", ""),
            actual_value=data.get("actual_value"),
            expected_value=data.get("expected_value", ""),
            timestamp=data.get("timestamp", time.time()),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Effect aggregator
# ---------------------------------------------------------------------------

@dataclass
class AggregatedEffects:
    """
    Aggregated view of all effects from a policy evaluation.

    Used to determine the overall outcome: ALLOW, REVIEW, or BLOCK.
    """

    effects: List[PolicyEffect] = field(default_factory=list)
    overall_outcome: str = "ALLOW"  # ALLOW, REVIEW, BLOCK
    highest_severity: EffectSeverity = EffectSeverity.NONE
    blocking_effects: List[PolicyEffect] = field(default_factory=list)
    review_effects: List[PolicyEffect] = field(default_factory=list)
    warning_effects: List[PolicyEffect] = field(default_factory=list)
    info_effects: List[PolicyEffect] = field(default_factory=list)

    @classmethod
    def aggregate(cls, effects: List[PolicyEffect]) -> "AggregatedEffects":
        """Aggregate a list of effects into a structured summary."""
        agg = cls(effects=effects)

        for effect in effects:
            if effect.is_blocking:
                agg.blocking_effects.append(effect)
            elif effect.requires_review:
                agg.review_effects.append(effect)
            elif effect.effect_type == EffectType.WARNING:
                agg.warning_effects.append(effect)
            else:
                agg.info_effects.append(effect)

            if effect.severity.value > agg.highest_severity.value:
                agg.highest_severity = effect.severity

        # Determine overall outcome
        if agg.blocking_effects:
            agg.overall_outcome = "BLOCK"
        elif agg.review_effects:
            agg.overall_outcome = "REVIEW"
        else:
            agg.overall_outcome = "ALLOW"

        return agg

    @property
    def is_blocking(self) -> bool:
        return self.overall_outcome == "BLOCK"

    @property
    def requires_review(self) -> bool:
        return self.overall_outcome == "REVIEW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_outcome": self.overall_outcome,
            "highest_severity": self.highest_severity.name,
            "total_effects": len(self.effects),
            "blocking_count": len(self.blocking_effects),
            "review_count": len(self.review_effects),
            "warning_count": len(self.warning_effects),
            "info_count": len(self.info_effects),
            "blocking_effects": [e.to_dict() for e in self.blocking_effects],
            "review_effects": [e.to_dict() for e in self.review_effects],
            "warning_effects": [e.to_dict() for e in self.warning_effects],
            "info_effects": [e.to_dict() for e in self.info_effects],
        }
