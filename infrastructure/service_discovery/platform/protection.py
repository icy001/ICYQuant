"""Platform protection for ICYQuant service discovery.

Provides ``PlatformProtection`` for safe mode, registry lock,
read-only mode, and emergency recovery to protect the platform
during failures.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class ProtectionMode(Enum):
    """Platform protection modes."""

    NORMAL = "normal"
    SAFE_MODE = "safe_mode"
    READ_ONLY = "read_only"
    LOCKED = "locked"
    EMERGENCY = "emergency"


class PlatformProtection:
    """Platform protection and safety mechanisms.

    Provides safe mode, registry lock, read-only mode,
    and emergency recovery to protect the platform during
    failures.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._mode = ProtectionMode.NORMAL
        self._mode_history: List[Dict[str, Any]] = []
        self._protection_count = 0
        self._recovery_callbacks: List[Callable] = []

    def set_mode(
        self,
        mode: ProtectionMode,
        reason: str = "",
        operator: str = "system",
    ) -> Dict[str, Any]:
        """Set the platform protection mode.

        Args:
            mode: The protection mode to activate.
            reason: Reason for the mode change.
            operator: Who triggered the change.

        Returns:
            Mode change result.
        """
        with self._lock:
            self._protection_count += 1
            old_mode = self._mode
            self._mode = mode

            record: Dict[str, Any] = {
                "old_mode": old_mode.value,
                "new_mode": mode.value,
                "reason": reason,
                "operator": operator,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._mode_history.append(record)
            if len(self._mode_history) > 100:
                self._mode_history = self._mode_history[-100:]

        logger.warning(
            "Protection mode changed: %s -> %s (reason=%s, operator=%s).",
            old_mode.value,
            mode.value,
            reason,
            operator,
        )
        return {
            "success": True,
            "old_mode": old_mode.value,
            "new_mode": mode.value,
            "reason": reason,
        }

    def activate_safe_mode(
        self, reason: str = ""
    ) -> Dict[str, Any]:
        return self.set_mode(
            ProtectionMode.SAFE_MODE,
            reason or "Entering safe mode",
        )

    def activate_read_only(
        self, reason: str = ""
    ) -> Dict[str, Any]:
        return self.set_mode(
            ProtectionMode.READ_ONLY,
            reason or "Switching to read-only mode",
        )

    def lock_registry(
        self, reason: str = ""
    ) -> Dict[str, Any]:
        return self.set_mode(
            ProtectionMode.LOCKED,
            reason or "Registry locked",
        )

    def emergency_recovery(
        self, reason: str = ""
    ) -> Dict[str, Any]:
        result = self.set_mode(
            ProtectionMode.EMERGENCY,
            reason or "Emergency recovery",
        )

        for cb in self._recovery_callbacks:
            try:
                cb(self._mode)
            except Exception as exc:
                logger.warning(
                    "Emergency callback failed: %s", exc
                )

        return result

    def restore_normal(
        self, reason: str = ""
    ) -> Dict[str, Any]:
        return self.set_mode(
            ProtectionMode.NORMAL,
            reason or "Restoring normal mode",
        )

    def is_normal(self) -> bool:
        with self._lock:
            return self._mode == ProtectionMode.NORMAL

    def is_read_only(self) -> bool:
        with self._lock:
            return self._mode in (
                ProtectionMode.READ_ONLY,
                ProtectionMode.SAFE_MODE,
            )

    def is_locked(self) -> bool:
        with self._lock:
            return self._mode == ProtectionMode.LOCKED

    def get_mode(self) -> ProtectionMode:
        with self._lock:
            return self._mode

    def on_emergency(self, callback: Callable) -> None:
        with self._lock:
            self._recovery_callbacks.append(callback)

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._mode_history)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_mode": self._mode.value,
                "is_normal": self._mode
                == ProtectionMode.NORMAL,
                "is_read_only": self.is_read_only(),
                "protection_count": self._protection_count,
                "mode_history": list(self._mode_history),
                "emergency_callbacks": len(
                    self._recovery_callbacks
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformProtection(mode={self._mode.value}, "
                f"changes={self._protection_count})"
            )
