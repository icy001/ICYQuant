"""
Dual-key transition for zero-downtime rotation.

Implements the dual-key rotation pattern
where both old and new credentials are
simultaneously active during a grace period,
enabling zero-downtime switches with
rollback safety.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TransitionPhase(str, Enum):
    """Dual-key transition phases."""

    INITIALIZING = "initializing"
    NEW_KEY_GENERATED = "new_key_generated"
    BOTH_ACTIVE = "both_active"
    VERIFYING = "verifying"
    ATOMIC_SWITCH = "atomic_switch"
    OLD_KEY_REVOKED = "old_key_revoked"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class TransitionState:
    """
    Tracks the state of a dual-key transition.

    Attributes:
        phase: Current transition phase.
        old_version: Old credential version.
        new_version: New credential version.
        old_value: Old credential value.
        new_value: New credential value.
        started_at: When transition started.
        completed_at: When transition completed.
        grace_ends_at: When grace period ends.
        steps: History of transition steps.
        verification_passed: Whether verification succeeded.
    """

    phase: TransitionPhase = TransitionPhase.INITIALIZING
    old_version: int = 1
    new_version: int = 2
    old_value: str = ""
    new_value: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    grace_ends_at: Optional[datetime] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    verification_passed: bool = False

    @property
    def is_complete(self) -> bool:
        """Check if transition is complete."""
        return self.phase == TransitionPhase.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if transition failed."""
        return self.phase in (TransitionPhase.FAILED, TransitionPhase.ROLLED_BACK)

    @property
    def is_in_grace_period(self) -> bool:
        """Check if currently in grace period."""
        if self.grace_ends_at is None:
            return False
        if self.phase not in (
            TransitionPhase.BOTH_ACTIVE,
            TransitionPhase.VERIFYING,
            TransitionPhase.ATOMIC_SWITCH,
        ):
            return False
        return datetime.utcnow() < self.grace_ends_at

    @property
    def grace_remaining(self) -> float:
        """Grace period remaining in seconds."""
        if self.grace_ends_at is None:
            return 0.0
        remaining = (self.grace_ends_at - datetime.utcnow()).total_seconds()
        return max(0.0, remaining)

    def advance_phase(
        self,
        new_phase: TransitionPhase,
        detail: str = "",
    ) -> None:
        """
        Advance to the next phase.

        Args:
            new_phase: New phase to enter.
            detail: Description of the phase transition.
        """
        self.steps.append({
            "from": self.phase.value,
            "to": new_phase.value,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        self.phase = new_phase

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "is_complete": self.is_complete,
            "is_failed": self.is_failed,
            "is_in_grace_period": self.is_in_grace_period,
            "grace_remaining_seconds": round(self.grace_remaining, 1),
            "started_at": self.started_at.isoformat() + "Z",
            "completed_at": (
                self.completed_at.isoformat() + "Z"
                if self.completed_at
                else None
            ),
            "verification_passed": self.verification_passed,
            "step_count": len(self.steps),
            "steps": self.steps[-10:],
        }


class DualKeyTransition:
    """
    Dual-key transition engine for zero-downtime rotation.

    Implements the rotation pattern:
    1. Generate new key (old key remains active)
    2. Both keys active during grace period
    3. Verify new key works
    4. Atomic switch to new key
    5. Revoke old key after grace period

    Usage:
        transition = DualKeyTransition(
            old_value="old-secret",
            new_value="new-secret",
            grace_period_days=7,
        )
        await transition.begin()
        await transition.verify(verify_fn)
        await transition.complete()
    """

    def __init__(
        self,
        old_value: str,
        new_value: str,
        old_version: int = 1,
        grace_period_days: int = 7,
        on_phase_change: Optional[Callable] = None,
    ) -> None:
        """
        Initialize dual-key transition.

        Args:
            old_value: Current secret value.
            new_value: New secret value.
            old_version: Current version number.
            grace_period_days: Grace period duration.
            on_phase_change: Callback for phase changes.
        """
        self._state = TransitionState(
            old_value=old_value,
            new_value=new_value,
            old_version=old_version,
            new_version=old_version + 1,
        )
        self._grace_period_days = grace_period_days
        self._on_phase_change = on_phase_change

    @property
    def state(self) -> TransitionState:
        """Get the current transition state."""
        return self._state

    def _advance(
        self,
        phase: TransitionPhase,
        detail: str = "",
    ) -> None:
        """Advance phase and notify listeners."""
        self._state.advance_phase(phase, detail)
        if self._on_phase_change:
            try:
                self._on_phase_change(self._state)
            except Exception as e:
                logger.error("Phase change callback error: %s", e)

    async def begin(self) -> TransitionState:
        """
        Begin the dual-key transition.

        Generates the new key and enters
        the both-active phase.

        Returns:
            Updated transition state.
        """
        self._advance(
            TransitionPhase.NEW_KEY_GENERATED,
            "New key generated",
        )

        # Set grace period
        self._state.grace_ends_at = (
            datetime.utcnow() + timedelta(days=self._grace_period_days)
        )

        self._advance(
            TransitionPhase.BOTH_ACTIVE,
            f"Both keys active (grace period: {self._grace_period_days} days)",
        )

        return self._state

    async def verify(
        self,
        verify_fn: Optional[Callable[[str], bool]] = None,
    ) -> bool:
        """
        Verify the new key works correctly.

        Args:
            verify_fn: Verification function that
                       tests the new value and returns bool.

        Returns:
            True if verification passed.
        """
        self._advance(TransitionPhase.VERIFYING, "Verifying new key")

        if verify_fn is None:
            # Default verification: check values differ and are non-empty
            passed = (
                self._state.new_value != self._state.old_value
                and len(self._state.new_value) > 0
            )
        else:
            try:
                passed = bool(verify_fn(self._state.new_value))
            except Exception as e:
                logger.error("Verification function error: %s", e)
                passed = False

        self._state.verification_passed = passed

        if not passed:
            self._advance(
                TransitionPhase.FAILED,
                "Verification failed",
            )
            logger.error(
                "Dual-key transition verification failed for version %d",
                self._state.new_version,
            )
        else:
            self._advance(
                TransitionPhase.ATOMIC_SWITCH,
                "Verification passed, performing atomic switch",
            )

        return passed

    async def complete(
        self,
        revoke_old: bool = True,
    ) -> TransitionState:
        """
        Complete the transition and revoke the old key.

        Args:
            revoke_old: Whether to revoke the old key.

        Returns:
            Final transition state.
        """
        if self._state.phase == TransitionPhase.FAILED:
            self._advance(
                TransitionPhase.ROLLED_BACK,
                "Transition failed, rolled back",
            )
            return self._state

        if revoke_old:
            self._advance(
                TransitionPhase.OLD_KEY_REVOKED,
                "Old key revoked",
            )

        self._state.completed_at = datetime.utcnow()
        self._advance(
            TransitionPhase.COMPLETED,
            "Dual-key transition completed successfully",
        )

        logger.info(
            "Dual-key transition completed: v%d -> v%d",
            self._state.old_version,
            self._state.new_version,
        )

        return self._state

    async def rollback(self) -> TransitionState:
        """
        Rollback the transition.

        Reverts to the old key and marks
        the transition as rolled back.

        Returns:
            Updated transition state.
        """
        self._advance(
            TransitionPhase.ROLLED_BACK,
            "Rollback initiated",
        )
        self._state.completed_at = datetime.utcnow()
        logger.warning(
            "Dual-key transition rolled back for version %d",
            self._state.new_version,
        )
        return self._state

    def get_phase_history(self) -> List[Dict[str, Any]]:
        """Get the full phase transition history."""
        return list(self._state.steps)
