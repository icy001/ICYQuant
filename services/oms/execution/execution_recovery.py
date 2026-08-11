"""ExecutionRecovery — recovers unknown execution states."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Optional

from .execution_gateway import ExecutionGateway
from .execution_report import ExecutionReport
from .execution_status import ExecutionStatus
from .execution_error import ExecutionUnknownError


class RecoveryTrigger(Enum):
    ACK_TIMEOUT = auto()
    SUBMISSION_TIMEOUT = auto()
    CANCEL_TIMEOUT = auto()
    REPORT_LOST = auto()
    STATE_MISMATCH = auto()
    MANUAL = auto()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass
class RecoveryResult:
    """Result of an execution recovery attempt."""
    order_id: str = ""
    trigger: RecoveryTrigger = RecoveryTrigger.MANUAL
    recovered: bool = False
    execution_status: ExecutionStatus = ExecutionStatus.UNKNOWN
    report: Optional[ExecutionReport] = None
    attempts: int = 0
    latency: float = 0.0
    error: str = ""


class ExecutionRecovery:
    """Recovers unknown execution states.

    When the OMS doesn't know the execution state of an order
    (e.g. after a timeout), the recovery manager queries the
    execution layer to determine the true state.

    CRITICAL: Recovery never invents execution facts. If the
    execution layer returns NOT_FOUND or UNKNOWN, the OMS
    must keep the order in UNKNOWN state.
    """

    def __init__(self, gateway: ExecutionGateway,
                 max_attempts: int = 3) -> None:
        self._gateway = gateway
        self._max_attempts = max_attempts
        self._recovery_cache: Dict[str, RecoveryResult] = {}

    def recover_submission(self, order_id: str,
                           trigger: RecoveryTrigger = RecoveryTrigger.SUBMISSION_TIMEOUT) -> RecoveryResult:
        """Recover the state of an order after a submission timeout."""
        start = time.time()
        result = RecoveryResult(order_id=order_id, trigger=trigger)

        for attempt in range(1, self._max_attempts + 1):
            result.attempts = attempt
            try:
                report = self._gateway.query_status(order_id)
                result.report = report
                result.execution_status = report.status

                if report.status != ExecutionStatus.UNKNOWN:
                    result.recovered = True
                    result.latency = time.time() - start
                    self._recovery_cache[order_id] = result
                    return result
            except Exception as e:
                result.error = str(e)

        result.latency = time.time() - start
        self._recovery_cache[order_id] = result
        return result

    def recover_cancel(self, order_id: str) -> RecoveryResult:
        """Recover the state of a cancel request."""
        return self.recover_submission(
            order_id, trigger=RecoveryTrigger.CANCEL_TIMEOUT,
        )

    def get_cached_result(self, order_id: str) -> Optional[RecoveryResult]:
        return self._recovery_cache.get(order_id)

    def clear_cache(self, order_id: str) -> None:
        self._recovery_cache.pop(order_id, None)
