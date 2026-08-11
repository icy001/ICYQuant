"""Execution Management System (EMS) — Institutional execution engine.

The EMS is responsible for HOW orders are executed, while the OMS
is responsible for managing orders. The EMS provides:

- Parent/Child Order Framework: large order decomposition
- Execution Engine: algorithm-driven order execution
- Execution Scheduler: multi-strategy scheduling with priority
- Algorithm Framework: TWAP, VWAP, POV, Iceberg, Arrival Price, Adaptive
- Execution Monitor: real-time fill rate, slippage, latency tracking
- Execution Quality: implementation shortfall analysis
- Execution Audit: immutable execution audit trail

Architecture::

    OMS → EMS → Execution Engine → Algorithm Layer → Broker Gateway → Exchange

Package exports::

    from services.ems import (
        ExecutionManagementSystem,
        ExecutionEngine,
        ExecutionRuntime,
        ExecutionManager,
    )
"""

from __future__ import annotations

from services.ems.execution_management_system import ExecutionManagementSystem
from services.ems.execution_engine import ExecutionEngine
from services.ems.execution_runtime import ExecutionRuntime
from services.ems.execution_manager import ExecutionManager
from services.ems.execution_controller import ExecutionController
from services.ems.execution_scheduler import ExecutionScheduler
from services.ems.execution_queue import ExecutionQueue
from services.ems.execution_context import ExecutionContext
from services.ems.execution_plan import ExecutionPlan
from services.ems.execution_policy import ExecutionPolicy
from services.ems.execution_state import ExecutionState, ExecutionStatus
from services.ems.execution_event import ExecutionEvent, ExecutionEventType
from services.ems.execution_metadata import ExecutionMetadata
from services.ems.execution_snapshot import ExecutionSnapshotManager
from services.ems.parent_order import ParentOrder, ParentOrderStatus
from services.ems.child_order import ChildOrder, ChildOrderStatus
from services.ems.parent_order_manager import ParentOrderManager
from services.ems.child_order_manager import ChildOrderManager
from services.ems.execution_dispatcher import ExecutionDispatcher
from services.ems.execution_monitor import ExecutionMonitor
from services.ems.execution_report import ExecutionReport
from services.ems.execution_statistics import ExecutionStatistics
from services.ems.execution_quality import ExecutionQualityAnalyzer
from services.ems.execution_audit import ExecutionAudit
from services.ems.metrics import EMSMetrics
from services.ems.telemetry import EMSTelemetry
from services.ems.diagnostics import EMSDiagnostics
from services.ems.health import EMSHealthChecker

__all__ = [
    "ExecutionManagementSystem",
    "ExecutionEngine",
    "ExecutionRuntime",
    "ExecutionManager",
    "ExecutionController",
    "ExecutionScheduler",
    "ExecutionQueue",
    "ExecutionContext",
    "ExecutionPlan",
    "ExecutionPolicy",
    "ExecutionState",
    "ExecutionStatus",
    "ExecutionEvent",
    "ExecutionEventType",
    "ExecutionMetadata",
    "ExecutionSnapshotManager",
    "ParentOrder",
    "ParentOrderStatus",
    "ChildOrder",
    "ChildOrderStatus",
    "ParentOrderManager",
    "ChildOrderManager",
    "ExecutionDispatcher",
    "ExecutionMonitor",
    "ExecutionReport",
    "ExecutionStatistics",
    "ExecutionQualityAnalyzer",
    "ExecutionAudit",
    "EMSMetrics",
    "EMSTelemetry",
    "EMSDiagnostics",
    "EMSHealthChecker",
]
