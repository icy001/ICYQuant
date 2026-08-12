"""
ControlScope — controls are never only global.

A control is scoped so an incident on one strategy, symbol or venue does not
force a system-wide halt (spec section 4):

    GLOBAL    → the whole trading system stops opening new orders
    ACCOUNT   → one account is forbidden from opening new orders
    PORTFOLIO → one portfolio is paused
    STRATEGY  → one strategy is stopped
    SYMBOL    → e.g. NVDA is forbidden from opening new positions
    VENUE     → one execution venue is disabled
    ORDER     → one specific order is controlled
"""

from __future__ import annotations

from enum import Enum


class ControlScope(str, Enum):
    GLOBAL = "GLOBAL"

    ACCOUNT = "ACCOUNT"

    PORTFOLIO = "PORTFOLIO"

    STRATEGY = "STRATEGY"

    SYMBOL = "SYMBOL"

    VENUE = "VENUE"

    ORDER = "ORDER"
