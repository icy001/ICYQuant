"""RecoveryPolicy — configuration for recovery operations."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryPolicy:
    """Policy for recovery operations.

    Defines:
      - Max attempts per recovery job
      - Whether auto-recovery is enabled
      - Whether to escalate on failure
    """

    max_attempts: int = 3
    auto_recovery_enabled: bool = True
    escalate_on_failure: bool = True
    query_timeout: float = 5.0

    @classmethod
    def default(cls) -> "RecoveryPolicy":
        return cls()

    @classmethod
    def aggressive(cls) -> "RecoveryPolicy":
        """More attempts, shorter timeout."""
        return cls(max_attempts=5, query_timeout=3.0)

    @classmethod
    def conservative(cls) -> "RecoveryPolicy":
        """Fewer attempts, longer timeout."""
        return cls(max_attempts=2, query_timeout=10.0)
