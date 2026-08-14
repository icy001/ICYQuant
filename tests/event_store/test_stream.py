"""Event stream model tests (Commit 34 Part 1.2 #2 / #14)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.event_store.domain.stream import (
    AppendRequest,
    EventStream,
    ensure_event_identity,
    validate_event_sequence,
)
from services.event_store.domain.errors import EventAlreadyExistsError


def test_event_stream_fields():
    stream = EventStream("ORD-001", "Order", 7)
    assert stream.aggregate_id == "ORD-001"
    assert stream.aggregate_type == "Order"
    assert stream.current_version == 7


def test_event_stream_next_version():
    assert EventStream("ORD-001", "Order", 7).next_version == 8
    assert EventStream("ORD-001", "Order", 0).next_version == 1


def test_event_stream_immutable():
    stream = EventStream("ORD-001", "Order", 7)
    with pytest.raises(FrozenInstanceError):
        stream.current_version = 8


def test_event_stream_validation():
    with pytest.raises(ValueError):
        EventStream("", "Order", 0)
    with pytest.raises(ValueError):
        EventStream("ORD-001", "", 0)
    with pytest.raises(ValueError):
        EventStream("ORD-001", "Order", -1)


def test_append_request_fields(make_events):
    events = make_events(versions=(8,))
    request = AppendRequest("ORD-001", 7, events)
    assert request.aggregate_id == "ORD-001"
    assert request.expected_version == 7
    assert request.events == events


def test_append_request_immutable(make_events):
    request = AppendRequest("ORD-001", 7, make_events(versions=(8,)))
    with pytest.raises(FrozenInstanceError):
        request.expected_version = 8


def test_validate_event_sequence_contiguous(make_events):
    # 7 -> 8 -> 9 -> 10 is legal
    events = make_events(versions=(8, 9, 10))
    validate_event_sequence(7, events)


def test_validate_event_sequence_gap_rejected(make_events):
    # 7 -> 8 -> 10 skips v9
    events = make_events(versions=(8, 10))
    with pytest.raises(ValueError):
        validate_event_sequence(7, events)


def test_validate_event_sequence_overlap_rejected(make_events):
    # 7 -> 9 -> 10 restarts at v9, skipping v8
    events = make_events(versions=(9, 10))
    with pytest.raises(ValueError):
        validate_event_sequence(7, events)


def test_validate_event_sequence_first_version(make_events):
    # expected=0 forces the first event to be v1
    events = make_events(versions=(2,))
    with pytest.raises(ValueError):
        validate_event_sequence(0, events)


def test_ensure_event_identity_missing_is_noop(make_stored_event):
    ensure_event_identity(None, make_stored_event())


def test_ensure_event_identity_same_payload_is_retry(make_stored_event):
    existing = make_stored_event(payload={"status": "CREATED"})
    incoming = make_stored_event(payload={"status": "CREATED"})
    ensure_event_identity(existing, incoming)  # no raise


def test_ensure_event_identity_different_payload_rejected(make_stored_event):
    existing = make_stored_event(payload={"status": "CREATED"})
    incoming = make_stored_event(payload={"status": "SUBMITTED"})
    with pytest.raises(EventAlreadyExistsError):
        ensure_event_identity(existing, incoming)


def test_sequential_append_advances_version(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))
    assert repository.current_version("ORD-001") == 1
    repository.append_stream("ORD-001", 1, make_events(versions=(2,)))
    assert repository.current_version("ORD-001") == 2
