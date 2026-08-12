"""
ControlRegistry — the in-memory registry of active ControlActions.

Registration is explicit and idempotent per control_id.  ``active()`` returns
every registered control matching a (scope, target) pair — the gateway is
responsible for priority resolution and expiration filtering so that the final
decision never depends on registration order (spec sections 6, 15 and 16).

Clearing is an explicit, authorized operation: a control leaves the registry
only through ``clear(control_id)`` (spec section 17 — explicit recovery, never
silent auto-recovery).
"""

from __future__ import annotations

from uuid import UUID

from .control import ControlAction
from .scope import ControlScope


class ControlRegistryError(Exception):
    """Raised when a control cannot be registered or managed."""


class ControlRegistry:

    def __init__(self):
        self._controls: list[ControlAction] = []

    def register(
        self,
        control: ControlAction,
    ) -> None:

        if not isinstance(control, ControlAction):
            raise ControlRegistryError(
                f"expected ControlAction, got {type(control).__name__}"
            )

        self._controls.append(control)

    def active(
        self,
        *,
        scope: ControlScope,
        target: str,
    ) -> list[ControlAction]:

        return [
            control
            for control in self._controls
            if (
                control.scope == scope
                and control.target == target
            )
        ]

    def get(
        self,
        control_id: UUID,
    ) -> ControlAction | None:

        for control in self._controls:
            if control.control_id == control_id:
                return control
        return None

    def clear(
        self,
        control_id,
    ) -> None:

        self._controls = [
            control
            for control in self._controls
            if control.control_id != control_id
        ]

    def all(self) -> list[ControlAction]:
        """Every registered control (active or otherwise), in registration order."""
        return list(self._controls)

    def count(self) -> int:
        return len(self._controls)

    def clear_all(self) -> None:
        self._controls = []
