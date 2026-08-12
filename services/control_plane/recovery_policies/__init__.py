"""
Recovery policies — decide *when* a recovery must start and at what scope.

These policies plug into the Policy Engine (Part 1.4).  They fire
``START_RECOVERY`` actions with a target scope; the actual recovery is
orchestrated by :class:`RecoveryOrchestrator`.
"""

from .event_recovery_policy import POLICY_ID as EVENT_RECOVERY_POLICY_ID
from .event_recovery_policy import build_event_recovery_policy
from .global_recovery_policy import POLICY_ID as GLOBAL_RECOVERY_POLICY_ID
from .global_recovery_policy import build_global_recovery_policy
from .ledger_recovery_policy import POLICY_ID as LEDGER_RECOVERY_POLICY_ID
from .ledger_recovery_policy import build_ledger_recovery_policy
from .position_recovery_policy import POLICY_ID as POSITION_RECOVERY_POLICY_ID
from .position_recovery_policy import build_position_recovery_policy

POLICIES = {
    POSITION_RECOVERY_POLICY_ID: build_position_recovery_policy,
    LEDGER_RECOVERY_POLICY_ID: build_ledger_recovery_policy,
    EVENT_RECOVERY_POLICY_ID: build_event_recovery_policy,
    GLOBAL_RECOVERY_POLICY_ID: build_global_recovery_policy,
}


def build_recovery_policies() -> list:
    """All recovery trigger policies, ready to register on an engine."""
    return [builder() for builder in POLICIES.values()]


def register_recovery_policies(engine) -> None:
    """Register every recovery policy on a :class:`PolicyEngine`."""
    for policy in build_recovery_policies():
        engine.register_policy(policy)


__all__ = [
    "POSITION_RECOVERY_POLICY_ID",
    "LEDGER_RECOVERY_POLICY_ID",
    "EVENT_RECOVERY_POLICY_ID",
    "GLOBAL_RECOVERY_POLICY_ID",
    "POLICIES",
    "build_position_recovery_policy",
    "build_ledger_recovery_policy",
    "build_event_recovery_policy",
    "build_global_recovery_policy",
    "build_recovery_policies",
    "register_recovery_policies",
]
