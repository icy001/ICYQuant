"""Commit 015 §12 — the account sync state machine.

    Broker connected
           ↓
        SYNCING          first snapshot requested
           ↓
        SYNCED           account + positions loaded, reconciled clean
           ↓  (no snapshot within max_sync_age)
        STALE

with ``MISMATCH`` (reconciliation failed, §11), ``ERROR`` (broker
failure) and ``OFFLINE`` (disconnected) as the degraded branches.

Illegal transitions raise :class:`InvalidAccountTransition` rather than
being silently allowed, so a bug in the sync wiring surfaces immediately.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from services.account.domain.enums import AccountStatus, now_cst
from services.account.sync.exceptions import InvalidAccountTransition

_T = AccountStatus

_TRANSITIONS: dict[str, frozenset[str]] = {
    _T.OFFLINE.value: frozenset({_T.CONNECTED.value, _T.ERROR.value}),
    _T.CONNECTED.value: frozenset(
        {
            _T.SYNCING.value,
            _T.STALE.value,
            _T.MISMATCH.value,
            _T.ERROR.value,
            _T.OFFLINE.value,
        }
    ),
    _T.SYNCING.value: frozenset(
        {
            _T.SYNCED.value,
            _T.STALE.value,
            _T.MISMATCH.value,
            _T.ERROR.value,
            _T.OFFLINE.value,
        }
    ),
    _T.SYNCED.value: frozenset(
        {
            _T.SYNCING.value,
            _T.STALE.value,
            _T.MISMATCH.value,
            _T.ERROR.value,
            _T.OFFLINE.value,
        }
    ),
    _T.STALE.value: frozenset(
        {
            _T.SYNCING.value,
            _T.SYNCED.value,
            _T.MISMATCH.value,
            _T.ERROR.value,
            _T.OFFLINE.value,
        }
    ),
    _T.MISMATCH.value: frozenset(
        {
            _T.SYNCING.value,
            _T.SYNCED.value,
            _T.STALE.value,
            _T.ERROR.value,
            _T.OFFLINE.value,
        }
    ),
    _T.ERROR.value: frozenset(
        {
            _T.CONNECTED.value,
            _T.SYNCING.value,
            _T.STALE.value,
            _T.OFFLINE.value,
        }
    ),
}


class AccountStateMachine:
    """Tracks one account's §12 status and its transition history."""

    def __init__(
        self,
        account_id: str,
        *,
        initial: Optional[str] = None,
        recorder: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.account_id = account_id
        self._state = str(initial or AccountStatus.OFFLINE.value)
        self._recorder = recorder
        self._history: list[tuple[str, str]] = []
        self._timeline: list[dict] = []

    # ── introspection ─────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def history(self) -> list[str]:
        """States visited, oldest → newest (excluding the initial)."""
        return [target for _, target in self._history]

    @property
    def timeline(self) -> list[dict]:
        return list(self._timeline)

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "state": self._state,
            "history": self.history,
            "timeline": self._timeline,
        }

    # ── transitions ───────────────────────────────────────────────────

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        if current == target:
            return True
        return target in _TRANSITIONS.get(str(current), frozenset())

    def can(self, target: str) -> bool:
        return self.can_transition(self._state, str(target))

    def to(self, target: str) -> str:
        """Transition to ``target``, raising on an illegal move (§12)."""
        target = str(target)
        if target == self._state:
            return self._state
        if not self.can_transition(self._state, target):
            raise InvalidAccountTransition(
                f"illegal account transition {self._state} → {target}",
                account_id=self.account_id,
                current=self._state,
                target=target,
            )
        self._apply(target)
        return self._state

    def force(self, target: str) -> str:
        """Transition without validation (recovery / reset paths)."""
        target = str(target)
        if target == self._state:
            return self._state
        self._apply(target)
        return self._state

    def _apply(self, target: str) -> None:
        previous = self._state
        self._state = target
        self._history.append((previous, target))
        self._timeline.append(
            {
                "from": previous,
                "to": target,
                "at": now_cst().isoformat(),
            }
        )
        if self._recorder is not None:
            self._recorder(previous, target)


__all__ = ["AccountStateMachine"]
