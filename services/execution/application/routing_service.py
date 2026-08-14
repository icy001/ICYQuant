from __future__ import annotations

from dataclasses import dataclass

from services.execution.application.adapter_registry import (
    ExecutionAdapterRegistry,
)
from services.execution.application.router import (
    ExecutionRouter,
)
from services.execution.domain.adapter_result import (
    AdapterSubmissionResult,
)
from services.execution.domain.request import (
    ExecutionRequest,
)
from services.execution.domain.routing import (
    ExecutionRoutingPolicy,
)


@dataclass(frozen=True)
class RoutingSubmissionResult:
    venue_id: str
    result: AdapterSubmissionResult


class RoutingExecutionService:

    def __init__(
        self,
        router: ExecutionRouter,
        registry: ExecutionAdapterRegistry,
    ) -> None:
        self._router = router
        self._registry = registry

    def submit(
        self,
        request: ExecutionRequest,
        policy: ExecutionRoutingPolicy,
    ) -> RoutingSubmissionResult:

        routed = self._router.route(
            request,
            policy,
        )

        adapter = self._registry.get(
            routed.venue.venue_id
        )

        result = adapter.submit(
            request
        )

        return RoutingSubmissionResult(
            venue_id=routed.venue.venue_id,
            result=result,
        )
