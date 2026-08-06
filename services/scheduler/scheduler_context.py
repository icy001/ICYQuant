"""Scheduler Context — provides execution context bridging scheduler to workflow engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .runtime.runtime_context import SchedulerContext as _SchedulerContext

# Re-export from runtime for convenience
SchedulerContext = _SchedulerContext


def create_scheduler_context(
    schedule_id: str,
    trace_id: Optional[str] = None,
    job_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    trigger_type: str = "manual",
    payload: Optional[Dict[str, Any]] = None,
) -> SchedulerContext:
    """Factory function to create a scheduler context.

    The context can be passed directly to the Workflow Engine
    for downstream execution, enabling full end-to-end tracing.

    Usage::

        ctx = create_scheduler_context("sch_001")
        # Pass to Workflow Engine
        await workflow_engine.execute(ctx)
    """
    return SchedulerContext(
        schedule_id=schedule_id,
        trace_id=trace_id or f"trace_{schedule_id}",
        job_id=job_id,
        execution_id=str(uuid.uuid4()),
        trigger_time=datetime.now(timezone.utc),
        trigger_type=trigger_type,
        worker_id=worker_id,
        payload=payload,
    )
