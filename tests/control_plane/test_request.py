"""Control request tests (Commit 29 Part 1.1 §6-7, §32).

Command and Request are separate: ``request_id`` belongs to Governance while
``command_id`` belongs to the Control Plane (§7). A request missing any
critical field is rejected and never reaches the dispatcher (§32).
"""

from datetime import datetime, timezone

import pytest

from services.control_plane.command import ControlCommand
from services.control_plane.errors import InvalidControlRequest
from services.control_plane.request import ControlRequest, validate_request
from services.control_plane.target import ControlTarget

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)

VALID_TARGET = ControlTarget(
    service="oms",
    instance="oms-primary",
    environment="production",
)


def make_command(**overrides):
    base = dict(
        command_id="CMD-001",
        resource="trading",
        action="pause",
        requested_by="ops-001",
        target=VALID_TARGET,
    )
    base.update(overrides)
    return ControlCommand(**base)


def make_request(**overrides):
    base = dict(
        request_id="REQ-001",
        command=make_command(),
        submitted_at=NOW,
        idempotency_key="IDEMP-001",
        source="ops-console",
    )
    base.update(overrides)
    return ControlRequest(**base)


class TestControlRequest:

    def test_request_and_command_ids_are_separate(self):
        """§7 — three-layer IDs must not be merged."""
        request = make_request()
        assert request.request_id == "REQ-001"
        assert request.command.command_id == "CMD-001"
        assert request.request_id != request.command.command_id

    def test_request_carries_command(self):
        command = make_command()
        request = make_request(command=command)
        assert request.command is command

    def test_request_carries_idempotency_key(self):
        request = make_request(idempotency_key="IDEMP-002")
        assert request.idempotency_key == "IDEMP-002"

    def test_request_carries_source(self):
        request = make_request(source="api")
        assert request.source == "api"


class TestRequestValidation:

    def test_accepts_complete_request(self):
        validate_request(make_request())  # should not raise

    def test_missing_request_id_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(request_id=""))

    def test_missing_idempotency_key_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(idempotency_key=""))

    def test_missing_source_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(source=""))

    def test_missing_submitted_at_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(submitted_at=None))

    def test_missing_command_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(command=None))

    def test_missing_command_id_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(
                make_request(command=make_command(command_id=""))
            )

    def test_missing_resource_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(
                make_request(command=make_command(resource=""))
            )

    def test_missing_action_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(make_request(command=make_command(action="")))

    def test_missing_requested_by_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(
                make_request(command=make_command(requested_by=""))
            )

    def test_missing_target_rejected(self):
        with pytest.raises(InvalidControlRequest):
            validate_request(
                make_request(command=make_command(target=None))
            )

    def test_rejection_reports_missing_fields(self):
        with pytest.raises(InvalidControlRequest) as excinfo:
            validate_request(make_request(request_id="", idempotency_key=""))
        message = str(excinfo.value)
        assert "request_id" in message
        assert "idempotency_key" in message
