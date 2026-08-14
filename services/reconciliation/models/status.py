from enum import Enum


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"


class ReconciliationLifecycle(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    REPAIR_PLANNED = "REPAIR_PLANNED"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
