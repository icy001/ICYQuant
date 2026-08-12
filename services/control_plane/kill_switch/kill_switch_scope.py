"""
KillSwitchScope — how narrowly a kill switch applies.

    GLOBAL       every new trading instruction, everywhere (highest priority)
    ACCOUNT      only instructions for a given account
    STRATEGY     only instructions from a given strategy
    INSTRUMENT   only instructions for a given instrument
    VENUE        only instructions routed to a given venue
    ORDER_FLOW   only a specific order flow

Priority (spec section 21):

    GLOBAL > ACCOUNT > STRATEGY > INSTRUMENT > VENUE
"""

from __future__ import annotations

from enum import Enum
from typing import List, Tuple


class KillSwitchScope(str, Enum):
    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"
    INSTRUMENT = "INSTRUMENT"
    VENUE = "VENUE"
    ORDER_FLOW = "ORDER_FLOW"


#: Evaluation priority — the first matching ACTIVE switch wins.
KILL_SWITCH_PRIORITY: Tuple[KillSwitchScope, ...] = (
    KillSwitchScope.GLOBAL,
    KillSwitchScope.ACCOUNT,
    KillSwitchScope.STRATEGY,
    KillSwitchScope.INSTRUMENT,
    KillSwitchScope.VENUE,
    KillSwitchScope.ORDER_FLOW,
)

__all__: List[str] = ["KillSwitchScope", "KILL_SWITCH_PRIORITY"]
