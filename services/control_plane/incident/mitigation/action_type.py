"""
MitigationActionType — the closed set of control actions the incident control
plane may dispatch against the ICYQuant trading stack (spec section 7).
"""

from __future__ import annotations

from enum import Enum


class MitigationActionType(str, Enum):

    CANCEL_OPEN_ORDERS = "CANCEL_OPEN_ORDERS"

    BLOCK_NEW_ORDERS = "BLOCK_NEW_ORDERS"

    REDUCE_POSITION = "REDUCE_POSITION"

    FLATTEN_POSITION = "FLATTEN_POSITION"

    DISABLE_STRATEGY = "DISABLE_STRATEGY"

    PAUSE_STRATEGY = "PAUSE_STRATEGY"

    REDUCE_RISK_LIMIT = "REDUCE_RISK_LIMIT"

    DISABLE_EXECUTION = "DISABLE_EXECUTION"

    KILL_SWITCH = "KILL_SWITCH"
