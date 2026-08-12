"""
PositionEffectValidator — verifies that a reduce-only order *actually* reduces
risk (spec sections 10/11/12).

Trusting the client's ``is_reduce_only=True`` flag is not enough: a caller
could mislabel ``BUY 100 is_reduce_only=True`` while increasing exposure.  The
validator recomputes the position effect from the current position, the side
and the quantity:

    Current Position = +100
        SELL 50  → REDUCE
        SELL 100 → FLATTEN
        BUY 50   → INCREASE

    Current Position = -100
        BUY 50   → REDUCE
        SELL 50  → INCREASE

The gateway's REDUCE_ONLY verdict plus an INCREASE effect must always equal a
REJECT — regardless of what the caller declared.
"""

from __future__ import annotations

from enum import Enum


class PositionEffect(str, Enum):

    INCREASE = "INCREASE"

    REDUCE = "REDUCE"

    FLATTEN = "FLATTEN"

    NONE = "NONE"


class PositionEffectValidator:

    def evaluate(
        self,
        current_position: float,
        side: str,
        quantity: float,
    ) -> PositionEffect:

        if current_position == 0:
            return PositionEffect.INCREASE

        signed_quantity = (
            quantity
            if side.upper() == "BUY"
            else -quantity
        )

        before = current_position
        after = (
            current_position
            + signed_quantity
        )

        if abs(after) < abs(before):

            if after == 0:
                return PositionEffect.FLATTEN

            return PositionEffect.REDUCE

        return PositionEffect.INCREASE
