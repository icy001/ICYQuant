"""
Controls — the unified control vocabulary (ControlType / ControlScope), the
declarative ControlAction model and the ControlRegistry.
"""

from __future__ import annotations

from .control import ControlAction, is_expired
from .control_type import ControlType
from .registry import ControlRegistry, ControlRegistryError
from .scope import ControlScope

__all__ = [
    "ControlAction",
    "ControlRegistry",
    "ControlRegistryError",
    "ControlScope",
    "ControlType",
    "is_expired",
]
