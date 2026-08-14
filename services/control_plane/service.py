"""Control service — the single business entry point (Commit 29 Part 1.2 §18-19).

External systems call ``ControlService.submit`` and never talk to the
Dispatcher, Executor or Handler directly. Every request flows through the
governed pipeline:

    External -> ControlService -> ControlPipeline -> Authorizer
             -> Governance -> Dispatcher -> Executor
"""

from __future__ import annotations

from .authorizer import AuthorizationGrant
from .pipeline import ControlPipeline
from .request import ControlRequest
from .result import ControlResult


class ControlService:
    """Sole business-facing facade for control operations (§18)."""

    def __init__(self, pipeline: ControlPipeline) -> None:
        self.pipeline = pipeline

    def submit(self, request: ControlRequest) -> ControlResult:
        """Authorise and execute a control request through the pipeline."""
        return self.pipeline.process(request)

    def submit_with_grant(
        self, request: ControlRequest, grant: AuthorizationGrant
    ) -> ControlResult:
        """Execute an already-approved command carrying an authorization grant."""
        return self.pipeline.submit_with_grant(request, grant)
