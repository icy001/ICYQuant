"""Control command dispatcher (Commit 29 Part 1.1 §18).

Dispatcher routes::

    Command -> Registry -> Handler

Unknown resource:action combinations surface as ``CommandNotFound`` so the
Control Plane fails closed instead of attempting a best-effort execution.
"""

from __future__ import annotations

from typing import Any

from .command import ControlCommand
from .errors import CommandNotFound


class ControlDispatcher:
    def __init__(self, registry: Any) -> None:
        self.registry = registry

    def dispatch(self, command: ControlCommand) -> Any:
        return self.dispatch_resource(command.resource, command.action)

    def dispatch_resource(self, resource: str, action: str) -> Any:
        try:
            return self.registry.resolve(resource, action)
        except LookupError as exc:
            raise CommandNotFound(str(exc)) from exc
