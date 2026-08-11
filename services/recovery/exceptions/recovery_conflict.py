"""Recovery conflict exceptions — concurrent job or version conflicts."""

from .recovery_error import RecoveryError


class RecoveryConflictError(RecoveryError):
    """Two recovery jobs conflict on the same recovery key."""

    def __init__(self, recovery_key: str, existing_job_id: str):
        self.recovery_key = recovery_key
        self.existing_job_id = existing_job_id
        super().__init__(
            f"Recovery conflict on key '{recovery_key}': "
            f"existing active job {existing_job_id}"
        )


class RecoveryLockedError(RecoveryError):
    """The target scope is locked by another recovery job."""

    def __init__(self, recovery_key: str, holder_job_id: str):
        self.recovery_key = recovery_key
        self.holder_job_id = holder_job_id
        super().__init__(
            f"Recovery key '{recovery_key}' is locked by job {holder_job_id}"
        )


class RecoveryConcurrentModificationError(RecoveryError):
    """Optimistic concurrency failure — expected version does not match current."""

    def __init__(
        self,
        domain: str,
        expected_version: int,
        current_version: int,
    ):
        self.domain = domain
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"{domain} version mismatch: expected {expected_version}, "
            f"got {current_version}"
        )
