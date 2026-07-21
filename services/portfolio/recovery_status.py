"""
Recovery status.
"""

from enum import Enum


class RecoveryStatus(Enum):

    SUCCESS = "SUCCESS"

    FAILED = "FAILED"

    RUNNING = "RUNNING"