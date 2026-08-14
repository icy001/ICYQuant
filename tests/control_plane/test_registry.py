"""Handler registry and idempotency registry tests (Commit 29 Part 1.1 §8-9, §28-30, §37-38).

* Duplicate handler registration is a startup/configuration error (§33).
* A resubmitted idempotency key with a different command fingerprint is a
  ``CommandConflict`` instead of a silent stale-result return (§29-30).
"""

from datetime import datetime, timezone

import pytest

from services.control_plane.command import ControlCommand, command_fingerprint
from services.control_plane.errors import CommandConflict
from services.control_plane.registry import (
    ControlRegistry,
    IdempotencyRegistry,
)
from services.control_plane.result import ControlResult
from services.control_plane.target import ControlTarget

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_command(action="pause"):
    return ControlCommand(
        command_id="CMD-001",
        resource="trading",
        action=action,
        requested_by="ops-001",
        target=ControlTarget(service="oms", instance="oms-primary"),
        created_at=NOW,
    )


def make_result(command_id="CMD-001"):
    return ControlResult(command_id=command_id, success=True)


class _Handler:
    def __init__(self, name):
        self.name = name

    def execute(self, command):
        return make_result(command.command_id)


class TestControlRegistry:

    def test_registry_resolves_handler(self):
        """§37."""
        registry = ControlRegistry()
        handler = _Handler("pause")
        registry.register("trading", "pause", handler)
        resolved = registry.resolve("trading", "pause")
        assert resolved is handler

    def test_duplicate_registration_rejected(self):
        """§38 — duplicate registration is a configuration error."""
        registry = ControlRegistry()
        registry.register("trading", "pause", _Handler("first"))
        with pytest.raises(ValueError):
            registry.register("trading", "pause", _Handler("second"))

    def test_missing_handler_raises_lookup_error(self):
        registry = ControlRegistry()
        with pytest.raises(LookupError):
            registry.resolve("trading", "pause")

    def test_has(self):
        registry = ControlRegistry()
        registry.register("trading", "pause", _Handler("pause"))
        assert registry.has("trading", "pause")
        assert not registry.has("trading", "kill")

    def test_commands_lists_registered_keys(self):
        registry = ControlRegistry()
        registry.register("trading", "pause", _Handler("pause"))
        registry.register("risk", "disable", _Handler("disable"))
        assert registry.commands() == [("risk", "disable"), ("trading", "pause")]

    def test_registration_key_uses_resource_and_action(self):
        """Different actions under the same resource are distinct commands."""
        registry = ControlRegistry()
        pause = _Handler("pause")
        kill = _Handler("kill")
        registry.register("trading", "pause", pause)
        registry.register("trading", "kill", kill)
        assert registry.resolve("trading", "pause") is pause
        assert registry.resolve("trading", "kill") is kill


class TestIdempotencyRegistry:

    def test_get_missing_returns_none(self):
        registry = IdempotencyRegistry()
        assert registry.get("IDEMP-001") is None

    def test_put_then_get_returns_result(self):
        registry = IdempotencyRegistry()
        result = make_result()
        registry.put("IDEMP-001", "fp-a", result)
        assert registry.get("IDEMP-001") is result

    def test_same_key_same_fingerprint_returns_existing_result(self):
        registry = IdempotencyRegistry()
        first = make_result()
        registry.put("IDEMP-001", "fp-a", first)
        returned = registry.put("IDEMP-001", "fp-a", make_result("OTHER"))
        assert returned is first

    def test_same_key_different_fingerprint_raises_conflict(self):
        registry = IdempotencyRegistry()
        registry.put("IDEMP-001", "fp-pause", make_result())
        with pytest.raises(CommandConflict):
            registry.put("IDEMP-001", "fp-kill", make_result("CMD-KILL"))

    def test_conflict_keeps_original_result(self):
        registry = IdempotencyRegistry()
        original = make_result()
        registry.put("IDEMP-001", "fp-pause", original)
        with pytest.raises(CommandConflict):
            registry.put("IDEMP-001", "fp-kill", make_result("CMD-KILL"))
        assert registry.get("IDEMP-001") is original

    def test_fingerprint_drives_conflict_detection(self):
        """A real command fingerprint changes when the action changes."""
        registry = IdempotencyRegistry()
        pause = make_command(action="pause")
        kill = make_command(action="kill")
        registry.put("IDEMP-001", command_fingerprint(pause), make_result())
        with pytest.raises(CommandConflict):
            registry.put("IDEMP-001", command_fingerprint(kill), make_result())
