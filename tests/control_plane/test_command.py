"""Control command model tests (Commit 29 Part 1.1 §4, §12, §29-30, §36).

Covers the immutable ``ControlCommand`` model, the command lifecycle state
default (``RECEIVED``), and the canonical command fingerprint used for
idempotency conflict detection.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.control_plane.command import ControlCommand, command_fingerprint
from services.control_plane.command_type import ControlCommandType
from services.control_plane.state import ControlState
from services.control_plane.target import ControlTarget

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_command(**overrides):
    base = dict(
        command_id="CMD-001",
        command_type=ControlCommandType.TRADING.value,
        resource="trading",
        action="pause",
        requested_by="ops-001",
        parameters={"reason": "scheduled maintenance"},
        target=ControlTarget(
            service="oms",
            instance="oms-primary",
            environment="production",
        ),
        created_at=NOW,
        correlation_id="CORR-001",
    )
    base.update(overrides)
    return ControlCommand(**base)


class TestControlCommand:

    def test_command_carries_all_fields(self):
        command = make_command()
        assert command.command_id == "CMD-001"
        assert command.command_type == ControlCommandType.TRADING.value
        assert command.resource == "trading"
        assert command.action == "pause"
        assert command.requested_by == "ops-001"
        assert command.parameters == {"reason": "scheduled maintenance"}
        assert command.target.service == "oms"
        assert command.target.instance == "oms-primary"
        assert command.created_at == NOW
        assert command.correlation_id == "CORR-001"

    def test_command_is_frozen(self):
        command = make_command()
        with pytest.raises(FrozenInstanceError):
            command.action = "kill"  # type: ignore[misc]

    def test_command_starts_received(self):
        """§36 — a command begins its lifecycle in RECEIVED."""
        command = make_command()
        assert command.state == ControlState.RECEIVED

    def test_empty_command_defaults_to_received(self):
        command = ControlCommand(command_id="CMD-000")
        assert command.state == ControlState.RECEIVED

    def test_with_state_returns_new_instance(self):
        command = make_command()
        advanced = command.with_state(ControlState.AUTHORIZING)
        assert advanced is not command
        assert advanced.state == ControlState.AUTHORIZING
        assert command.state == ControlState.RECEIVED
        assert advanced.command_id == command.command_id


class TestCommandFingerprint:

    def test_fingerprint_stable_for_identical_command(self):
        assert command_fingerprint(make_command()) == command_fingerprint(
            make_command()
        )

    def test_fingerprint_changes_with_action(self):
        assert command_fingerprint(
            make_command(action="pause")
        ) != command_fingerprint(make_command(action="kill"))

    def test_fingerprint_changes_with_resource(self):
        assert command_fingerprint(
            make_command(resource="trading")
        ) != command_fingerprint(make_command(resource="execution"))

    def test_fingerprint_changes_with_target(self):
        assert command_fingerprint(
            make_command(
                target=ControlTarget(
                    service="oms",
                    instance="oms-primary",
                    environment="production",
                )
            )
        ) != command_fingerprint(
            make_command(
                target=ControlTarget(
                    service="oms",
                    instance="oms-secondary",
                    environment="production",
                )
            )
        )

    def test_fingerprint_changes_with_parameters(self):
        assert command_fingerprint(
            make_command(parameters={"reason": "maintenance"})
        ) != command_fingerprint(make_command(parameters={"reason": "incident"}))

    def test_fingerprint_changes_with_requested_by(self):
        assert command_fingerprint(
            make_command(requested_by="ops-001")
        ) != command_fingerprint(make_command(requested_by="ops-002"))

    def test_fingerprint_ignores_metadata(self):
        """created_at / correlation_id / command_id are not part of §30."""
        assert command_fingerprint(make_command()) == command_fingerprint(
            make_command(correlation_id="CORR-999")
        )


class TestControlCommandType:

    def test_all_types_present(self):
        values = [member.value for member in ControlCommandType]
        assert values == [
            "TRADING",
            "RISK",
            "RECONCILIATION",
            "LEDGER",
            "POSITION",
            "STRATEGY",
            "SYSTEM",
        ]
