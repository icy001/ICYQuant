"""Shadow Trading domain (Commit 016).

Deliberately imports **no** execution / service module here: the
execution package imports this domain, so re-exporting the service
from the package root would create an import cycle.  Import the
service directly::

    from services.shadow.service import ShadowTradingService
"""
from services.shadow.shadow_account import ShadowAccount, ShadowAccountError
from services.shadow.shadow_config import ShadowConfig
from services.shadow.shadow_gate import (
    ShadowGate,
    ShadowGateCheck,
    ShadowGateDecision,
    ShadowGateReason,
)
from services.shadow.shadow_ledger import (
    ShadowEvent,
    ShadowEventLedger,
    ShadowEventType,
)
from services.shadow.shadow_pnl import ShadowPnL
from services.shadow.shadow_position import ShadowPosition, ShadowPositionBook

__all__ = [
    "ShadowAccount",
    "ShadowAccountError",
    "ShadowConfig",
    "ShadowGate",
    "ShadowGateCheck",
    "ShadowGateDecision",
    "ShadowGateReason",
    "ShadowEvent",
    "ShadowEventLedger",
    "ShadowEventType",
    "ShadowPnL",
    "ShadowPosition",
    "ShadowPositionBook",
]
