"""Shadow execution package (Commit 016 §5).

The only execution surface of Commit 016.  Nothing in this package
may import a broker order API — that is the §25 structural guarantee,
verified by the safety test matrix.
"""
from services.execution.shadow.shadow_fill import ShadowFill, ShadowFillStatus
from services.execution.shadow.shadow_order import (
    OrderIntent,
    OrderSide,
    OrderType,
    ShadowOrder,
    ShadowOrderStatus,
    new_intent_id,
)
from services.execution.shadow.shadow_execution import ShadowExecution

__all__ = [
    "OrderIntent",
    "OrderSide",
    "OrderType",
    "ShadowExecution",
    "ShadowFill",
    "ShadowFillStatus",
    "ShadowOrder",
    "ShadowOrderStatus",
    "new_intent_id",
]
