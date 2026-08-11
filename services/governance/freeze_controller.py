"""
Freeze Controller — manages governance freezes at various scopes.

Part 1.5: supports targeted freezes (GLOBAL, PORTFOLIO, STRATEGY,
ASSET, ACCOUNT, ORDER) to contain risk without affecting unrelated
operations.

Key principle: Freeze new risk, NOT risk reduction.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class FreezeScope(Enum):
    """Scope of a freeze."""

    GLOBAL = auto()       # Entire platform
    PORTFOLIO = auto()    # Specific portfolio
    STRATEGY = auto()     # Specific strategy
    ASSET = auto()        # Specific asset/instrument
    ACCOUNT = auto()      # Specific account
    ORDER = auto()        # Specific order type


class FreezeController:
    """Manages governance freezes at defined scopes.

    Supports precise freezes so "one strategy problem" does not
    freeze the entire platform.
    """

    def __init__(self):
        # Active freezes: scope → set of target IDs
        self._active_freezes: Dict[FreezeScope, Set[str]] = {
            scope: set() for scope in FreezeScope
        }
        self._global_frozen: bool = False
        self._freeze_history: List[Dict[str, Any]] = []

    @property
    def is_global_frozen(self) -> bool:
        return self._global_frozen

    def freeze(
        self,
        scope: str = "GLOBAL",
        target: str = "",
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Apply a freeze at the given scope.

        Args:
            scope: "GLOBAL", "PORTFOLIO", "STRATEGY", "ASSET", "ACCOUNT", "ORDER"
            target: Target identifier (portfolio_id, strategy_id, etc.)
            reason: Why the freeze is applied
            correlation_id: For audit tracing
        """
        scope_map = {
            "GLOBAL": FreezeScope.GLOBAL,
            "PORTFOLIO": FreezeScope.PORTFOLIO,
            "STRATEGY": FreezeScope.STRATEGY,
            "ASSET": FreezeScope.ASSET,
            "ACCOUNT": FreezeScope.ACCOUNT,
            "ORDER": FreezeScope.ORDER,
        }

        try:
            scope_enum = scope_map.get(scope.upper(), FreezeScope.GLOBAL)
        except (KeyError, AttributeError):
            scope_enum = FreezeScope.GLOBAL

        freeze_record = {
            "freeze_id": f"FRZ-{uuid.uuid4().hex[:12].upper()}",
            "scope": scope_enum.name,
            "target": target,
            "reason": reason,
            "correlation_id": correlation_id,
            "applied_at": time.time(),
            "status": "ACTIVE",
        }

        if scope_enum == FreezeScope.GLOBAL:
            self._global_frozen = True
        else:
            self._active_freezes[scope_enum].add(target if target else "*")

        self._freeze_history.append(freeze_record)
        return {"status": "FROZEN", **freeze_record}

    def unfreeze(
        self,
        scope: str = "GLOBAL",
        target: str = "",
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Remove a freeze."""
        try:
            scope_enum_str = scope.upper()
            if isinstance(scope, FreezeScope):
                scope_enum = scope
            else:
                scope_map = {
                    "GLOBAL": FreezeScope.GLOBAL,
                    "PORTFOLIO": FreezeScope.PORTFOLIO,
                    "STRATEGY": FreezeScope.STRATEGY,
                    "ASSET": FreezeScope.ASSET,
                    "ACCOUNT": FreezeScope.ACCOUNT,
                    "ORDER": FreezeScope.ORDER,
                }
                scope_enum = scope_map.get(scope_enum_str, FreezeScope.GLOBAL)
        except (KeyError, AttributeError):
            scope_enum = FreezeScope.GLOBAL

        if scope_enum == FreezeScope.GLOBAL:
            self._global_frozen = False
        else:
            if target and target in self._active_freezes[scope_enum]:
                self._active_freezes[scope_enum].discard(target)
            elif not target:
                self._active_freezes[scope_enum].clear()

        return {"status": "UNFROZEN", "scope": scope_enum.name, "target": target, "reason": reason}

    def is_frozen(
        self,
        scope: Optional[str] = None,
        target: str = "",
    ) -> bool:
        """Check if a given scope/target is frozen."""
        if self._global_frozen:
            return True

        if scope is None:
            return False

        try:
            scope_map = {
                "GLOBAL": FreezeScope.GLOBAL,
                "PORTFOLIO": FreezeScope.PORTFOLIO,
                "STRATEGY": FreezeScope.STRATEGY,
                "ASSET": FreezeScope.ASSET,
                "ACCOUNT": FreezeScope.ACCOUNT,
                "ORDER": FreezeScope.ORDER,
            }
            scope_enum = scope_map.get(scope.upper(), FreezeScope.GLOBAL)
        except (KeyError, AttributeError):
            return self._global_frozen

        if not target:
            return len(self._active_freezes[scope_enum]) > 0

        return (target in self._active_freezes[scope_enum] or
                "*" in self._active_freezes[scope_enum])

    def cancel_pending(
        self,
        reason: str = "",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        """Cancel all pending orders."""
        record = {
            "action_id": f"CNL-{uuid.uuid4().hex[:12].upper()}",
            "action": "CANCEL_PENDING",
            "reason": reason,
            "correlation_id": correlation_id,
            "timestamp": time.time(),
        }
        return {"status": "CANCELLED", **record}

    def get_active_freezes(self) -> Dict[str, Any]:
        """Get summary of active freezes."""
        freezes = {"GLOBAL": self._global_frozen}
        for scope, targets in self._active_freezes.items():
            if scope != FreezeScope.GLOBAL:
                freezes[scope.name] = sorted(list(targets))
        return freezes

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "global_frozen": self._global_frozen,
            "active_freezes": self.get_active_freezes(),
            "total_freezes": len(self._freeze_history),
        }
