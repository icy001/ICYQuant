"""
Operational Policy Engine — the component that answers:

    "now that the system found an anomaly, what should it do?"

Health feeds the engine; the engine produces a PolicyDecision and a set of
PolicyActions; the Trading Gate turns those into ALLOW / DENY per order.
"""

from .policy import Policy, PolicyResult
from .policy_action import PolicyAction, PolicyActionType
from .policy_condition import (
    CompositeCondition,
    ConditionConnective,
    ConditionOperator,
    PolicyCondition,
    and_,
    condition,
    evaluate_condition,
    not_,
    or_,
)
from .policy_context import (
    KillSwitchState,
    MarketDataFreshness,
    PolicyContext,
    RecoveryState,
)
from .policy_decision import (
    FAIL_SAFE_RANK,
    PolicyDecision,
    is_at_least,
    is_more_severe,
    most_severe,
    sorted_by_severity,
)
from .policy_engine import (
    ManualOverride,
    OverrideScope,
    PolicyEngine,
    PolicyEvaluation,
)
from .policy_priority import (
    PolicyPriority,
    highest_priority,
    lowest_priority,
    priority_ge,
    sorted_priorities,
)
from .policy_rule import (
    PolicyRule,
    PolicyRuleResult,
    action,
)

__all__ = [
    "Policy",
    "PolicyResult",
    "PolicyAction",
    "PolicyActionType",
    "PolicyCondition",
    "CompositeCondition",
    "ConditionOperator",
    "ConditionConnective",
    "condition",
    "and_",
    "or_",
    "not_",
    "evaluate_condition",
    "PolicyContext",
    "MarketDataFreshness",
    "KillSwitchState",
    "RecoveryState",
    "PolicyDecision",
    "FAIL_SAFE_RANK",
    "most_severe",
    "is_at_least",
    "is_more_severe",
    "sorted_by_severity",
    "PolicyPriority",
    "priority_ge",
    "highest_priority",
    "lowest_priority",
    "sorted_priorities",
    "PolicyRule",
    "PolicyRuleResult",
    "action",
    "PolicyEngine",
    "PolicyEvaluation",
    "OverrideScope",
    "ManualOverride",
]
