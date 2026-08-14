"""Dispatcher tests (Commit 29 Part 1.1 §18).

Dispatcher routes ``Command -> Registry -> Handler``; unknown commands surface
as ``CommandNotFound`` so the Control Plane fails closed.
"""

from datetime import datetime, timezone

import pytest

from services.control_plane.command import ControlCommand
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.errors import CommandNotFound
from services.control_plane.registry import ControlRegistry
from services.control_plane.target import ControlTarget

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_command(resource="trading", action="pause"):
    return ControlCommand(
        command_id="CMD-001",
        resource=resource,
        action=action,
        requested_by="ops-001",
        target=ControlTarget(service="oms", instance="oms-primary"),
        created_at=NOW,
    )


class _Handler:
    def __init__(self, name):
        self.name = name

    def execute(self, command):
        return command


def make_dispatcher(*pairs):
    registry = ControlRegistry()
    for (resource, action), handler in pairs:
        registry.register(resource, action, handler)
    return ControlDispatcher(registry)


class TestControlDispatcher:

    def test_dispatch_resolves_handler(self):
        handler = _Handler("pause")
        dispatcher = make_dispatcher((("trading", "pause"), handler))
        resolved = dispatcher.dispatch(make_command())
        assert resolved is handler

    def test_dispatch_uses_resource_and_action(self):
        pause = _Handler("pause")
        kill = _Handler("kill")
        dispatcher = make_dispatcher(
            (("trading", "pause"), pause),
            (("trading", "kill"), kill),
        )
        assert dispatcher.dispatch(make_command(action="pause")) is pause
        assert dispatcher.dispatch(make_command(action="kill")) is kill

    def test_dispatch_resource_dispatches_by_key(self):
        handler = _Handler("pause")
        dispatcher = make_dispatcher((("trading", "pause"), handler))
        assert dispatcher.dispatch_resource("trading", "pause") is handler

    def test_unknown_command_raises_command_not_found(self):
        dispatcher = make_dispatcher()
        with pytest.raises(CommandNotFound):
            dispatcher.dispatch(make_command(resource="unknown", action="destroy"))

    def test_unknown_action_raises_command_not_found(self):
        handler = _Handler("pause")
        dispatcher = make_dispatcher((("trading", "pause"), handler))
        with pytest.raises(CommandNotFound):
            dispatcher.dispatch(make_command(action="rebuild"))
