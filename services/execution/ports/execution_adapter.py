from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.adapter_result import (
    AdapterSubmissionResult,
)
from services.execution.domain.request import (
    ExecutionRequest,
)


class ExecutionAdapter(ABC):
    """
    Port between Execution Engine and external execution venue.
    """

    @abstractmethod
    def submit(
        self,
        request: ExecutionRequest,
    ) -> AdapterSubmissionResult:
        raise NotImplementedError

    @abstractmethod
    def cancel(
        self,
        external_order_id: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_status(
        self,
        external_order_id: str,
    ) -> str:
        raise NotImplementedError
