"""TimeoutManager — tracks and detects execution timeouts."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

from .timeout_policy import TimeoutPolicy


class TimeoutType(Enum):
    SUBMISSION = auto()
    ACK = auto()
    CANCEL = auto()
    EXECUTION_REPORT = auto()
    QUERY = auto()

    @property
    def label(self) -> str:
        return self.name.title()


@dataclass
class TimeoutRecord:
    """Record of a timeout event."""
    order_id: str = ""
    request_id: str = ""
    timeout_type: TimeoutType = TimeoutType.SUBMISSION
    started_at: float = field(default_factory=lambda: __import__("time").time())
    expired_at: float = 0.0
    detected: bool = False

    @property
    def is_expired(self) -> bool:
        if self.expired_at <= 0:
            return False
        return time.time() >= self.expired_at


class TimeoutManager:
    """Manages execution timeouts.

    When a timeout is detected, the manager does NOT automatically
    fail the order — it marks it as UNKNOWN and triggers recovery.
    """

    def __init__(self, policy: Optional[TimeoutPolicy] = None) -> None:
        self._policy = policy or TimeoutPolicy.default()
        self._records: Dict[str, TimeoutRecord] = {}  # key = order_id:type

    def start(self, order_id: str, timeout_type: TimeoutType,
              request_id: str = "") -> TimeoutRecord:
        """Start tracking a timeout for an order."""
        key = self._key(order_id, timeout_type)
        timeout_duration = self._get_timeout(timeout_type)
        record = TimeoutRecord(
            order_id=order_id,
            request_id=request_id,
            timeout_type=timeout_type,
            started_at=time.time(),
            expired_at=time.time() + timeout_duration,
        )
        self._records[key] = record
        return record

    def cancel(self, order_id: str, timeout_type: TimeoutType) -> None:
        """Cancel a timeout (e.g. ACK received)."""
        key = self._key(order_id, timeout_type)
        self._records.pop(key, None)

    def check_expired(self, order_id: str,
                      timeout_type: TimeoutType) -> bool:
        """Check if a timeout has expired for an order."""
        key = self._key(order_id, timeout_type)
        record = self._records.get(key)
        if record is None:
            return False
        if record.is_expired:
            record.detected = True
            return True
        return False

    def check_all_expired(self) -> List[TimeoutRecord]:
        """Check all timeouts and return expired ones."""
        expired = []
        for record in self._records.values():
            if record.is_expired and not record.detected:
                record.detected = True
                expired.append(record)
        return expired

    def get_record(self, order_id: str,
                   timeout_type: TimeoutType) -> Optional[TimeoutRecord]:
        return self._records.get(self._key(order_id, timeout_type))

    def clear(self, order_id: str) -> None:
        """Clear all timeouts for an order."""
        keys_to_remove = [k for k in self._records if k.startswith(f"{order_id}:")]
        for k in keys_to_remove:
            self._records.pop(k, None)

    @staticmethod
    def _key(order_id: str, timeout_type: TimeoutType) -> str:
        return f"{order_id}:{timeout_type.name}"

    def _get_timeout(self, timeout_type: TimeoutType) -> float:
        _map = {
            TimeoutType.SUBMISSION: self._policy.submission_timeout,
            TimeoutType.ACK: self._policy.ack_timeout,
            TimeoutType.CANCEL: self._policy.cancel_timeout,
            TimeoutType.EXECUTION_REPORT: self._policy.execution_report_timeout,
            TimeoutType.QUERY: self._policy.query_timeout,
        }
        return _map[timeout_type]
