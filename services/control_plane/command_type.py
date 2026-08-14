"""Control command taxonomy (Commit 29 Part 1.1 §5).

The first phase does not push business logic into the Control Plane; it only
identifies, validates, authorises, routes, and tracks. ``ControlCommandType``
tags the *kind* of control being requested.
"""

from enum import Enum


class ControlCommandType(str, Enum):
    TRADING = "TRADING"
    RISK = "RISK"
    RECONCILIATION = "RECONCILIATION"
    LEDGER = "LEDGER"
    POSITION = "POSITION"
    STRATEGY = "STRATEGY"
    SYSTEM = "SYSTEM"
