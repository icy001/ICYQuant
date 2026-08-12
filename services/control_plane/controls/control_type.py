"""
ControlType — the unified control vocabulary of the Institutional Control
Gateway.

Every subsystem that can affect trading — Risk Engine, OMS, Execution Engine,
Strategy Runtime and the Incident Control Plane — speaks the same control
semantics (spec section 3):

    Risk Engine / OMS / Execution / Strategy / Incident
        └──────────────────────┬──────────────────────┘
                               ▼
                       Control Vocabulary
"""

from __future__ import annotations

from enum import Enum


class ControlType(str, Enum):
    NORMAL = "NORMAL"

    REDUCE_ONLY = "REDUCE_ONLY"

    BLOCK_NEW_ORDERS = "BLOCK_NEW_ORDERS"

    CANCEL_OPEN_ORDERS = "CANCEL_OPEN_ORDERS"

    PAUSE_STRATEGY = "PAUSE_STRATEGY"

    DISABLE_STRATEGY = "DISABLE_STRATEGY"

    DISABLE_EXECUTION = "DISABLE_EXECUTION"

    KILL_SWITCH = "KILL_SWITCH"
