"""Durable command store (Commit 29 Part 1.3 §8-10, §31, §35-37).

A ``CommandRecord`` is the durable view of a control command. Every write
through ``transition`` is a Compare-And-Swap on ``version``::

    UPDATE control_commands
    SET state = :new_state, version = version + 1
    WHERE command_id = :command_id AND version = :expected_version;

A zero affected-rows result means the expected version is stale and is
surfaced as ``VersionConflict`` — the last-writer-wins overwrite that could
silently erase another worker's ``EXECUTING -> SUCCEEDED`` is impossible
(§9-10, §36-37).

``CommandStore`` is the protocol; ``InMemoryCommandStore`` is the reference
implementation. PostgreSQL / event-store adapters are a later part (§35).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol

from .errors import CommandRecordNotFound, DuplicateCommand, VersionConflict
from .transition import StateTransitionEngine


@dataclass(frozen=True)
class CommandRecord:
    """Immutable durable record of one control command (§8)."""

    command_id: str
    request_id: str
    state: str
    version: int
    updated_at: datetime
    correlation_id: str
    authorization_decision_id: str | None = None

    def with_state(
        self,
        new_state: str,
        version: int,
        *,
        updated_at: datetime | None = None,
    ) -> "CommandRecord":
        return replace(
            self,
            state=new_state,
            version=version,
            updated_at=updated_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class StateTransition:
    """One recorded command state change (§31)."""

    command_id: str
    from_state: str
    to_state: str
    version: int
    changed_at: datetime
    reason: str


class CommandStore(Protocol):
    """Durable, versioned command store interface (§35)."""

    def create(self, record: CommandRecord) -> None: ...

    def save(self, record: CommandRecord) -> None: ...

    def get(self, command_id: str) -> CommandRecord: ...

    def transition(
        self,
        command_id: str,
        expected_version: int,
        new_state: str,
        *,
        reason: str = "state_change",
        changed_at: datetime | None = None,
    ) -> CommandRecord: ...

    def history(self, command_id: str) -> tuple[StateTransition, ...]: ...


class InMemoryCommandStore:
    """Reference ``CommandStore`` backed by process memory."""

    def __init__(
        self,
        *,
        transition_engine: StateTransitionEngine | None = None,
    ) -> None:
        self._records: dict[str, CommandRecord] = {}
        self._history: dict[str, list[StateTransition]] = {}
        self.transition_engine = transition_engine or StateTransitionEngine()

    def create(self, record: CommandRecord) -> None:
        """Persist a brand-new command; duplicate ids are rejected."""
        if record.command_id in self._records:
            raise DuplicateCommand(
                f"command {record.command_id} already exists"
            )
        self._records[record.command_id] = record
        self._history.setdefault(record.command_id, [])

    def save(self, record: CommandRecord) -> None:
        """Unconditional durable write — recovery bootstrap (§38).

        Used when a crashed process restores a checkpoint; it intentionally
        bypasses optimistic concurrency because there is no live writer yet.
        """
        self._records[record.command_id] = record
        self._history.setdefault(record.command_id, [])

    def get(self, command_id: str) -> CommandRecord:
        try:
            return self._records[command_id]
        except KeyError:
            raise CommandRecordNotFound(
                f"no durable record for command {command_id}"
            ) from None

    def transition(
        self,
        command_id: str,
        expected_version: int,
        new_state: str,
        *,
        reason: str = "state_change",
        changed_at: datetime | None = None,
    ) -> CommandRecord:
        record = self.get(command_id)
        if record.version != expected_version:
            raise VersionConflict(
                f"command {command_id}: expected version {expected_version}, "
                f"actual version {record.version} (state {record.state})"
            )
        # Defence in depth: even the persistence layer refuses to persist an
        # illegal jump (§45.1).
        self.transition_engine.transition(record.state, new_state)
        changed = changed_at or datetime.now(timezone.utc)
        new_record = record.with_state(
            new_state,
            record.version + 1,
            updated_at=changed,
        )
        self._records[command_id] = new_record
        self._history.setdefault(command_id, []).append(
            StateTransition(
                command_id=command_id,
                from_state=record.state,
                to_state=new_state,
                version=new_record.version,
                changed_at=changed,
                reason=reason,
            )
        )
        return new_record

    def history(self, command_id: str) -> tuple[StateTransition, ...]:
        return tuple(self._history.get(command_id, ()))
