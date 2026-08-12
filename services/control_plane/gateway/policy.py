"""
GatewayPolicy — how the gateway behaves under failure and which controls it
must honour.

Defaults (spec section 10/18):

    * fail_safe_state = FAIL_SAFE  → when the gateway breaks it moves to
      FAIL_SAFE, which blocks new orders instead of silently allowing them.
    * fail_open = False            → fail-closed is the safe default.  fail_open
      must be an explicit, conscious opt-in.
    * require_control_registry = True → a registry failure is treated as a
      gateway failure (fail-safe), never as "no controls → allow".

Control Precedence (spec section 15):

    KILL_SWITCH > DISABLE_EXECUTION > BLOCK_NEW_ORDERS > DISABLE_STRATEGY
    > REDUCE_ONLY > PAUSE_STRATEGY > NORMAL

    i.e. BLOCK > REDUCE_ONLY > ALLOW.  The gateway resolves the final decision
    from priority, never from registration order.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..controls.control_type import ControlType
from .state import GatewayState

CONTROL_PRIORITY = {
    ControlType.KILL_SWITCH: 1000,
    ControlType.DISABLE_EXECUTION: 900,
    ControlType.BLOCK_NEW_ORDERS: 800,
    ControlType.DISABLE_STRATEGY: 700,
    ControlType.REDUCE_ONLY: 600,
    ControlType.PAUSE_STRATEGY: 500,
    ControlType.NORMAL: 0,
}


@dataclass(frozen=True)
class GatewayPolicy:

    fail_safe_state: GatewayState = (
        GatewayState.FAIL_SAFE
    )

    fail_open: bool = False

    require_control_registry: bool = True
