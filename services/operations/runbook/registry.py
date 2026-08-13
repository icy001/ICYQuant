"""Runbook registry and standard production runbooks (Commit 27 Part 1.5,
spec sections 14-24, 33).

Version lock（spec section 33）:

    Incident 创建时锁定 Runbook 版本（如 RB-RECON-001 v1.2.0），
    整个 Incident 生命周期不能突然切换到新版本。

第一批标准 Runbook（spec section 15）:

    RB-SERVICE-001  Service Unhealthy
    RB-EVENTBUS-001 Event Bus Failure
    RB-RECON-001    Reconciliation Difference
    RB-VENUE-001    Venue Connectivity Failure
    RB-EXEC-001     Execution Degradation
    RB-RISK-001     Risk Engine Failure
    RB-RECOVERY-001 Trading Recovery
    RB-KILL-001     Emergency Trading Halt
"""

from __future__ import annotations

from .action import RunbookAction
from .models import RunbookSeverity
from .runbook import RunbookDefinition, RunbookValidator
from .step import RunbookStep, StepType


class RunbookRegistry:

    def __init__(
        self,
        validator: RunbookValidator | None = None,
    ):

        self._validator = validator or RunbookValidator()

        self._runbooks = {}

    def register(
        self,
        runbook: RunbookDefinition,
    ) -> RunbookDefinition:
        """注册前强制校验（spec section 34）。"""

        self._validator.validate(runbook)

        key = (
            runbook.runbook_id,
            runbook.version,
        )

        self._runbooks[key] = runbook

        return runbook

    def get(
        self,
        runbook_id: str,
        version: str,
    ) -> RunbookDefinition | None:

        return self._runbooks.get(
            (runbook_id, version)
        )

    def latest(
        self,
        runbook_id: str,
    ) -> RunbookDefinition | None:
        """返回指定 runbook_id 最新注册的版本。"""

        versions = [
            runbook
            for (rid, _), runbook
            in self._runbooks.items()
            if rid == runbook_id
        ]

        if not versions:
            return None

        return versions[-1]

    def all(self) -> tuple[RunbookDefinition, ...]:

        return tuple(
            self._runbooks.values()
        )

    def versions(
        self,
        runbook_id: str,
    ) -> tuple[str, ...]:

        return tuple(
            version
            for (rid, version)
            in self._runbooks.keys()
            if rid == runbook_id
        )


# ----------------------------------------------------------------
# Standard runbooks
# ----------------------------------------------------------------

def _step(
    order: int,
    step_id: str,
    name: str,
    step_type: StepType,
    description: str,
) -> RunbookStep:

    return RunbookStep(
        step_id=step_id,
        order=order,
        name=name,
        step_type=step_type,
        description=description,
    )


def _action(
    step_id: str,
    name: str,
    control_action: str,
    requires_approval: bool = True,
) -> RunbookAction:

    return RunbookAction(
        action_id=step_id,
        name=name,
        control_action=control_action,
        requires_approval=requires_approval,
    )


def _rb_service_unhealthy() -> RunbookDefinition:
    """RB-SERVICE-001 Service Unhealthy（spec section 16）。"""

    steps = (
        _step(1, "svc-01", "Service health", StepType.CHECK, "Service health"),
        _step(2, "svc-02", "Dependency health", StepType.CHECK, "Dependency health"),
        _step(3, "svc-03", "Recent deployment", StepType.CHECK, "Recent deployment"),
        _step(4, "svc-04", "Error rate", StepType.CHECK, "Error rate"),
        _step(5, "svc-05", "Event backlog", StepType.CHECK, "Event backlog"),
        _step(6, "svc-06", "Restart / Failover", StepType.ACTION, "Restart / Failover if permitted"),
        _step(7, "svc-07", "Stabilization", StepType.WAIT, "Stabilization"),
        _step(8, "svc-08", "Health recovery", StepType.VALIDATION, "Health recovery"),
        _step(9, "svc-09", "Trading safety", StepType.VALIDATION, "Trading safety"),
    )

    actions = (
        _action("svc-06", "Restart / Failover", "FAILOVER_SERVICE"),
    )

    return RunbookDefinition(
        runbook_id="RB-SERVICE-001",
        name="Service Unhealthy",
        description="Generic service health degradation runbook",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_eventbus_failure() -> RunbookDefinition:
    """RB-EVENTBUS-001 Event Bus Failure（spec section 17）。

    Event Bus 恢复 ≠ 可以立即恢复交易：
    必须经过 Ledger + Position + Reconciliation。
    """

    steps = (
        _step(1, "eb-01", "Event Bus health", StepType.CHECK, "Event Bus health"),
        _step(2, "eb-02", "Consumer lag", StepType.CHECK, "Consumer lag"),
        _step(3, "eb-03", "Producer failures", StepType.CHECK, "Producer failures"),
        _step(4, "eb-04", "Stop new trading", StepType.ACTION, "Stop new trading if required"),
        _step(5, "eb-05", "Activate failover", StepType.ACTION, "Activate failover"),
        _step(6, "eb-06", "Event flow stabilization", StepType.WAIT, "Event flow stabilization"),
        _step(7, "eb-07", "Event sequence", StepType.VALIDATION, "Event sequence"),
        _step(8, "eb-08", "Ledger consistency", StepType.VALIDATION, "Ledger consistency"),
        _step(9, "eb-09", "Position consistency", StepType.VALIDATION, "Position consistency"),
        _step(10, "eb-10", "Reconciliation", StepType.VALIDATION, "Reconciliation"),
        _step(11, "eb-11", "Resume trading", StepType.APPROVAL, "Resume trading"),
    )

    actions = (
        _action("eb-04", "Stop new trading", "PAUSE_TRADING"),
        _action("eb-05", "Activate failover", "FAILOVER_EVENT_BUS"),
    )

    return RunbookDefinition(
        runbook_id="RB-EVENTBUS-001",
        name="Event Bus Failure",
        description="Event bus outage / degradation runbook",
        severity=RunbookSeverity.CRITICAL,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_reconciliation() -> RunbookDefinition:
    """RB-RECON-001 Reconciliation Difference（spec sections 18-19）。

    Position = 当前状态；Ledger = 为什么变成这个状态。
    Position != Ledger 时不能强行覆盖，必须:

        Detect -> Investigate -> Rebuild -> Reconcile -> Validate
    """

    steps = (
        _step(1, "rc-01", "Ledger", StepType.CHECK, "Ledger"),
        _step(2, "rc-02", "Position", StepType.CHECK, "Position"),
        _step(3, "rc-03", "Event sequence", StepType.CHECK, "Event sequence"),
        _step(4, "rc-04", "Missing events", StepType.CHECK, "Missing events"),
        _step(5, "rc-05", "Freeze affected trading", StepType.ACTION, "Freeze affected trading"),
        _step(6, "rc-06", "Start reconstruction", StepType.ACTION, "Start reconstruction"),
        _step(7, "rc-07", "Ledger rebuilt", StepType.VALIDATION, "Ledger rebuilt"),
        _step(8, "rc-08", "Position rebuilt", StepType.VALIDATION, "Position rebuilt"),
        _step(9, "rc-09", "Reconciliation passed", StepType.VALIDATION, "Reconciliation passed"),
        _step(10, "rc-10", "Risk exposure valid", StepType.VALIDATION, "Risk exposure valid"),
        _step(11, "rc-11", "Resume trading", StepType.APPROVAL, "Resume trading"),
    )

    actions = (
        _action("rc-05", "Freeze affected trading", "PAUSE_TRADING"),
        _action("rc-06", "Start reconstruction", "START_RECONSTRUCTION"),
    )

    return RunbookDefinition(
        runbook_id="RB-RECON-001",
        name="Reconciliation Difference",
        description="Position / Ledger mismatch runbook",
        severity=RunbookSeverity.CRITICAL,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_venue_failure() -> RunbookDefinition:
    """RB-VENUE-001 Venue Connectivity Failure（spec section 20）。"""

    steps = (
        _step(1, "vn-01", "Heartbeat", StepType.CHECK, "Heartbeat"),
        _step(2, "vn-02", "Latency", StepType.CHECK, "Latency"),
        _step(3, "vn-03", "Reject rate", StepType.CHECK, "Reject rate"),
        _step(4, "vn-04", "Cancel status", StepType.CHECK, "Cancel status"),
        _step(5, "vn-05", "Open orders", StepType.CHECK, "Open orders"),
        _step(6, "vn-06", "Stop routing", StepType.ACTION, "Stop routing"),
        _step(7, "vn-07", "Failover", StepType.ACTION, "Failover"),
        _step(8, "vn-08", "Alternate venue", StepType.VALIDATION, "Alternate venue"),
        _step(9, "vn-09", "Order state", StepType.VALIDATION, "Order state"),
        _step(10, "vn-10", "Position", StepType.VALIDATION, "Position"),
        _step(11, "vn-11", "Stabilization", StepType.WAIT, "Stabilization"),
        _step(12, "vn-12", "Resume", StepType.APPROVAL, "Resume"),
    )

    actions = (
        _action("vn-06", "Stop routing", "STOP_VENUE_ROUTING"),
        _action("vn-07", "Failover", "FAILOVER_VENUE"),
    )

    return RunbookDefinition(
        runbook_id="RB-VENUE-001",
        name="Venue Connectivity Failure",
        description="Venue connectivity degradation runbook",
        severity=RunbookSeverity.ELEVATED,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_execution_degradation() -> RunbookDefinition:
    """RB-EXEC-001 Execution Degradation（spec section 21）。

    触发: execution_latency_high + execution_failure_spike
    """

    steps = (
        _step(1, "ex-01", "Execution queue", StepType.CHECK, "Execution queue"),
        _step(2, "ex-02", "Broker / Venue", StepType.CHECK, "Broker / Venue"),
        _step(3, "ex-03", "Network", StepType.CHECK, "Network"),
        _step(4, "ex-04", "Order state", StepType.CHECK, "Order state"),
        _step(5, "ex-05", "Reduce routing", StepType.ACTION, "Reduce routing"),
        _step(6, "ex-06", "Pause affected strategy", StepType.ACTION, "Pause affected strategy"),
        _step(7, "ex-07", "Outstanding orders", StepType.VALIDATION, "Outstanding orders"),
        _step(8, "ex-08", "Positions", StepType.VALIDATION, "Positions"),
        _step(9, "ex-09", "Resume gradually", StepType.APPROVAL, "Resume gradually"),
    )

    actions = (
        _action("ex-05", "Reduce routing", "REDUCE_ROUTING"),
        _action("ex-06", "Pause affected strategy", "PAUSE_STRATEGY"),
    )

    return RunbookDefinition(
        runbook_id="RB-EXEC-001",
        name="Execution Degradation",
        description="Execution latency / failure degradation runbook",
        severity=RunbookSeverity.ELEVATED,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_risk_failure() -> RunbookDefinition:
    """RB-RISK-001 Risk Engine Failure（spec section 22）。

    必须区分:

        Block New Orders
        Liquidate Existing Positions

    后者是更高等级的 Control Action，不能因普通 Risk Service
    故障就自动执行。
    """

    steps = (
        _step(1, "rk-01", "Risk availability", StepType.CHECK, "Risk availability"),
        _step(2, "rk-02", "Order admission safety", StepType.CHECK, "Can new orders be safely evaluated?"),
        _step(3, "rk-03", "Block new orders", StepType.ACTION, "Block new orders"),
        _step(4, "rk-04", "Positions observable", StepType.CHECK, "Existing positions remain observable"),
        _step(5, "rk-05", "Risk state", StepType.VALIDATION, "Validate risk state"),
        _step(6, "rk-06", "Recover Risk", StepType.ACTION, "Recover Risk service"),
        _step(7, "rk-07", "Replay / Reconcile", StepType.ACTION, "Replay / Reconcile state"),
        _step(8, "rk-08", "Risk validation", StepType.VALIDATION, "Risk validation passed"),
        _step(9, "rk-09", "Resume trading", StepType.APPROVAL, "Resume trading"),
    )

    actions = (
        _action("rk-03", "Block new orders", "PAUSE_TRADING"),
        _action("rk-06", "Recover Risk", "RESTART_SERVICE"),
        _action("rk-07", "Replay / Reconcile", "START_RECONSTRUCTION"),
    )

    return RunbookDefinition(
        runbook_id="RB-RISK-001",
        name="Risk Engine Failure",
        description="Risk engine unavailable runbook",
        severity=RunbookSeverity.CRITICAL,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_trading_recovery() -> RunbookDefinition:
    """RB-RECOVERY-001 Trading Recovery（spec section 24）。

    与 recovery.py 的统一 Recovery Checklist 一一对应。
    """

    steps = (
        _step(1, "rv-01", "Service health", StepType.CHECK, "Service health"),
        _step(2, "rv-02", "Event Bus healthy", StepType.CHECK, "Event Bus healthy"),
        _step(3, "rv-03", "Ledger healthy", StepType.CHECK, "Ledger healthy"),
        _step(4, "rv-04", "Position healthy", StepType.CHECK, "Position healthy"),
        _step(5, "rv-05", "Risk healthy", StepType.CHECK, "Risk healthy"),
        _step(6, "rv-06", "OMS healthy", StepType.CHECK, "OMS healthy"),
        _step(7, "rv-07", "Execution healthy", StepType.CHECK, "Execution healthy"),
        _step(8, "rv-08", "Venue connected", StepType.CHECK, "Venue connected"),
        _step(9, "rv-09", "No unresolved critical alerts", StepType.CHECK, "No unresolved critical alerts"),
        _step(10, "rv-10", "Reconciliation passed", StepType.VALIDATION, "Reconciliation passed"),
        _step(11, "rv-11", "Risk validation passed", StepType.VALIDATION, "Risk validation passed"),
        _step(12, "rv-12", "Open order validation passed", StepType.VALIDATION, "Open order validation passed"),
        _step(13, "rv-13", "Position validation passed", StepType.VALIDATION, "Position validation passed"),
        _step(14, "rv-14", "Recovery approval", StepType.APPROVAL, "Recovery approval"),
        _step(15, "rv-15", "Resume trading", StepType.ACTION, "Resume trading"),
    )

    actions = (
        _action("rv-15", "Resume trading", "RESUME_TRADING"),
    )

    return RunbookDefinition(
        runbook_id="RB-RECOVERY-001",
        name="Trading Recovery",
        description="Trading recovery gate runbook",
        severity=RunbookSeverity.CRITICAL,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


def _rb_emergency_halt() -> RunbookDefinition:
    """RB-KILL-001 Emergency Trading Halt（spec section 23）。

    Kill 之后不是结束，而是进入 Recovery。
    """

    steps = (
        _step(1, "kl-01", "Catastrophic event", StepType.CHECK, "Catastrophic event detected"),
        _step(2, "kl-02", "Global trading halt", StepType.ACTION, "Global trading halt"),
        _step(3, "kl-03", "Freeze order admission", StepType.ACTION, "Freeze new order admission"),
        _step(4, "kl-04", "Outstanding orders", StepType.VALIDATION, "Outstanding orders"),
        _step(5, "kl-05", "Positions", StepType.VALIDATION, "Positions"),
        _step(6, "kl-06", "Ledger", StepType.VALIDATION, "Ledger"),
        _step(7, "kl-07", "Risk", StepType.VALIDATION, "Risk"),
        _step(8, "kl-08", "Root cause investigation", StepType.CHECK, "Investigate root cause"),
        _step(9, "kl-09", "Recover infrastructure", StepType.ACTION, "Recover infrastructure"),
        _step(10, "kl-10", "State reconciled", StepType.VALIDATION, "Reconcile state"),
        _step(11, "kl-11", "Resume trading", StepType.APPROVAL, "Resume trading"),
    )

    actions = (
        _action("kl-02", "Global trading halt", "KILL_TRADING"),
        _action("kl-03", "Freeze order admission", "FREEZE_ORDER_ADMISSION"),
        _action("kl-09", "Recover infrastructure", "START_RECOVERY"),
    )

    return RunbookDefinition(
        runbook_id="RB-KILL-001",
        name="Emergency Trading Halt",
        description="Catastrophic event global trading halt runbook",
        severity=RunbookSeverity.EMERGENCY,
        version="1.0.0",
        steps=steps,
        actions=actions,
    )


_STANDARD_RUNBOOK_BUILDERS = (
    _rb_service_unhealthy,
    _rb_eventbus_failure,
    _rb_reconciliation,
    _rb_venue_failure,
    _rb_execution_degradation,
    _rb_risk_failure,
    _rb_trading_recovery,
    _rb_emergency_halt,
)


def build_standard_runbooks() -> tuple[RunbookDefinition, ...]:
    """spec section 15: 第一批标准生产 Runbook。"""

    return tuple(
        builder()
        for builder in _STANDARD_RUNBOOK_BUILDERS
    )


def register_standard_runbooks(
    registry: RunbookRegistry,
) -> RunbookRegistry:
    """把标准 Runbook 注册进 Registry（注册前自动校验）。"""

    for runbook in build_standard_runbooks():
        registry.register(runbook)

    return registry
