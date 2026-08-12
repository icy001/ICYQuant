"""
GatewayState — the operational posture of the Institutional Control Gateway
itself.

A production-grade principle (spec section 9/18):

    When the gateway itself fails it must NOT default to allowing every order.
    The default posture is fail-closed (FAIL_SAFE) so that high-risk trading
    actions are blocked until the gateway is explicitly recovered.
"""

from __future__ import annotations

from enum import Enum


class GatewayState(str, Enum):
    HEALTHY = "HEALTHY"

    DEGRADED = "DEGRADED"

    FAIL_SAFE = "FAIL_SAFE"

    DISABLED = "DISABLED"

    @property
    def blocks_new_orders(self) -> bool:
        """Does this state hard-block new order admission by itself?"""
        return self in {GatewayState.FAIL_SAFE, GatewayState.DISABLED}
