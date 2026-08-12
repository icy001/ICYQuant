"""
MitigationPolicy — which control actions apply per severity and whether they
run automatically or behind an approval (spec section 10).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..incident_severity import IncidentSeverity
from .action_type import MitigationActionType


@dataclass(frozen=True)
class MitigationPolicy:

    actions: tuple[MitigationActionType, ...]

    automatic: bool = True

    approval_required: bool = False


DEFAULT_MITIGATION_POLICIES = {

    IncidentSeverity.INFO: MitigationPolicy(
        actions=(MitigationActionType.PAUSE_STRATEGY,),
        automatic=True,
    ),

    IncidentSeverity.LOW: MitigationPolicy(
        actions=(MitigationActionType.PAUSE_STRATEGY,),
        automatic=True,
    ),

    IncidentSeverity.MEDIUM: MitigationPolicy(
        actions=(
            MitigationActionType.CANCEL_OPEN_ORDERS,
            MitigationActionType.PAUSE_STRATEGY,
        ),
        automatic=True,
    ),

    IncidentSeverity.HIGH: MitigationPolicy(
        actions=(
            MitigationActionType.CANCEL_OPEN_ORDERS,
            MitigationActionType.BLOCK_NEW_ORDERS,
            MitigationActionType.REDUCE_RISK_LIMIT,
        ),
        automatic=True,
        approval_required=True,
    ),

    IncidentSeverity.CRITICAL: MitigationPolicy(
        actions=(
            MitigationActionType.CANCEL_OPEN_ORDERS,
            MitigationActionType.BLOCK_NEW_ORDERS,
            MitigationActionType.DISABLE_STRATEGY,
            MitigationActionType.DISABLE_EXECUTION,
        ),
        automatic=True,
        approval_required=True,
    ),

    IncidentSeverity.FATAL: MitigationPolicy(
        actions=(
            MitigationActionType.CANCEL_OPEN_ORDERS,
            MitigationActionType.BLOCK_NEW_ORDERS,
            MitigationActionType.DISABLE_STRATEGY,
            MitigationActionType.DISABLE_EXECUTION,
            MitigationActionType.FLATTEN_POSITION,
            MitigationActionType.KILL_SWITCH,
        ),
        automatic=True,
        approval_required=True,
    ),
}
