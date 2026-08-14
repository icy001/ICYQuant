"""Strategy execution readiness checks.

A check answers one narrow question against a single
:class:`~services.strategy.readiness.state.ReadinessContext` snapshot.
Checks are classified as *hard* gates (a failure means the strategy must not
trade: risk, execution, lifecycle, ...) or *soft* gates (a failure merely
degrades the strategy: secondary data, analytics, optional features, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

from services.strategy.readiness.state import ReadinessContext


@dataclass(frozen=True)
class CheckResult:
    """The verdict of a single readiness check."""

    passed: bool
    hard: bool = True
    reasons: tuple[str, ...] = ()


class ReadinessCheck:
    """Base class for a single readiness check."""

    name: str = "readiness"

    def check(self, context: ReadinessContext) -> CheckResult:  # pragma: no cover
        raise NotImplementedError


def _verdict(passed: bool, name: str, detail: str, hard: bool = True) -> CheckResult:
    return CheckResult(
        passed=passed,
        hard=hard,
        reasons=() if passed else (detail,),
    )


class LifecycleCheck(ReadinessCheck):
    """The strategy must be in the RUNNING lifecycle state.

    ``PAUSED`` (or any other lifecycle state) directly results in NOT_READY /
    BLOCKED - the strategy is not allowed to enter the execution pipeline.
    """

    name = "lifecycle"

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.control_state == "RUNNING"
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"lifecycle state is {context.control_state}",
        )


class RuntimeCheck(ReadinessCheck):
    """The strategy runtime must be RUNNING and observable.

    ``Control=RUNNING, Runtime=UNKNOWN`` therefore results in execution being
    blocked - the system must not assume a strategy is trading when the
    runtime cannot confirm it.
    """

    name = "runtime"

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.runtime_state == "RUNNING"
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"runtime state is {context.runtime_state}",
        )


class MarketDataReadinessCheck(ReadinessCheck):
    """The primary market data feed must be connected and fresh.

    First-stage checks: feed connected, feed fresh, required symbols
    available and timestamps valid.  A stale feed (e.g. last tick three
    minutes ago while the strategy requires five seconds) blocks execution.
    """

    name = "market_data"

    _GOOD_STATES = frozenset({"FRESH", "READY", "CONNECTED"})

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.market_data_state in self._GOOD_STATES
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"market data state is {context.market_data_state}",
        )


class ConfigurationCheck(ReadinessCheck):
    """The strategy configuration must be complete and valid.

    First-stage checks: strategy id, universe, timeframe, parameters, risk
    profile and execution profile.  ``RUNNING + INVALID`` configuration is
    never acceptable.
    """

    name = "configuration"

    _GOOD_STATES = frozenset({"VALID", "READY"})

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.configuration_state in self._GOOD_STATES
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"configuration state is {context.configuration_state}",
        )


class RiskReadinessCheck(ReadinessCheck):
    """The risk engine must allow the strategy to run.

    First-stage checks: risk engine available, risk profile valid, exposure
    limit available, daily loss limit not breached and the strategy not
    risk-blocked.  A ``BLOCKED`` risk gate is a hard gate that no ordinary
    check can override.
    """

    name = "risk"

    _GOOD_STATES = frozenset({"ALLOWED", "OK", "HEALTHY"})

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.risk_state in self._GOOD_STATES
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"risk state is {context.risk_state}",
        )


class ExecutionConnectivityCheck(ReadinessCheck):
    """Execution infrastructure (OMS / execution engine / broker) must be up.

    A disconnected execution engine means ``READY`` can never hold.
    """

    name = "execution"

    _GOOD_STATES = frozenset({"CONNECTED", "READY"})

    def check(self, context: ReadinessContext) -> CheckResult:
        passed = context.execution_state in self._GOOD_STATES
        return _verdict(
            passed=passed,
            name=self.name,
            detail=f"execution state is {context.execution_state}",
        )


DEFAULT_READINESS_CHECKS: tuple[ReadinessCheck, ...] = (
    LifecycleCheck(),
    RuntimeCheck(),
    MarketDataReadinessCheck(),
    ConfigurationCheck(),
    RiskReadinessCheck(),
    ExecutionConnectivityCheck(),
)
