"""
AdmissionPolicy — the configuration of Order Admission (spec section 5).

Defaults enforce the production posture:

    * Risk must approve (require_risk_approval=True)
    * Control must approve (require_control_approval=True)
    * reduce-only flows are allowed (allow_reduce_only=True)
    * a gateway failure rejects new orders (reject_on_gateway_failure=True)
    * zero / negative quantities are rejected
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdmissionPolicy:

    require_risk_approval: bool = True

    require_control_approval: bool = True

    allow_reduce_only: bool = True

    reject_on_gateway_failure: bool = True

    reject_zero_quantity: bool = True

    reject_negative_quantity: bool = True
