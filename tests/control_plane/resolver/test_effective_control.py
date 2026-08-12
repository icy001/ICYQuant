"""
Tests for EffectiveControlResolver (Commit 26 Part 1.5, spec section 23).

核心断言：New Risk 路径与 Risk Reduction 路径必须分开计算——
Kill Switch 不是 "STOP EVERYTHING"，而是
"STOP RISK CREATION, PRESERVE RISK REDUCTION"。
"""

from uuid import uuid4

from services.control_plane.admission.decision import (
    AdmissionDecision,
    AdmissionReason,
    OrderAdmissionDecision,
)
from services.control_plane.admission.risk import (
    RiskDecision,
    RiskResult,
)
from services.control_plane.execution import ExecutionState
from services.control_plane.execution.decision import (
    ExecutionControlDecision,
)
from services.control_plane.global_control import GlobalControlState
from services.control_plane.global_control.decision import (
    GlobalControlDecision,
)
from services.control_plane.portfolio import PortfolioState
from services.control_plane.portfolio.decision import (
    PortfolioControlDecision,
)
from services.control_plane.resolver import EffectiveControlResolver
from services.control_plane.strategy import StrategyState
from services.control_plane.strategy.decision import (
    StrategyControlDecision,
)
from services.control_plane.venue import VenueState
from services.control_plane.venue.decision import (
    VenueControlDecision,
)


def _global_allowed() -> GlobalControlDecision:
    return GlobalControlDecision(
        state=GlobalControlState.NORMAL,
        allow_new_risk=True,
        allow_new_orders=True,
        allow_cancel_orders=True,
        allow_reduce_orders=True,
        allow_emergency_flatten=True,
        allow_recovery=False,
        reason="global_normal",
    )


def _portfolio_allowed() -> PortfolioControlDecision:
    return PortfolioControlDecision(
        portfolio_id="pf_1",
        current_state=PortfolioState.ACTIVE,
        allow_new_risk=True,
        allow_new_orders=True,
        allow_reduce_orders=True,
        allow_liquidation=True,
        reason="portfolio_active",
    )


def _strategy_allowed() -> StrategyControlDecision:
    return StrategyControlDecision(
        strategy_id="strat_1",
        current_state=StrategyState.RUNNING,
        allow_signal_generation=True,
        allow_new_orders=True,
        allow_reduce_orders=True,
        reason="strategy_running",
    )


def _execution_allowed() -> ExecutionControlDecision:
    return ExecutionControlDecision(
        execution_id="exec_1",
        state=ExecutionState.ACTIVE,
        allow_new_orders=True,
        allow_cancel_orders=True,
        allow_reduce_orders=True,
        allow_emergency_flatten=True,
        reason="execution_active",
    )


def _venue_allowed() -> VenueControlDecision:
    return VenueControlDecision(
        venue="NASDAQ",
        state=VenueState.ONLINE,
        allow_new_orders=True,
        allow_cancel_orders=True,
        allow_reduce_orders=True,
        allow_emergency_flatten=True,
        reason="venue_online",
    )


def _accepted_admission() -> OrderAdmissionDecision:
    return OrderAdmissionDecision(
        decision=AdmissionDecision.ACCEPTED,
        reason=AdmissionReason.CONTROL_ALLOWED,
        request_id=uuid4(),
    )


def _approved_risk() -> RiskResult:
    return RiskResult(decision=RiskDecision.APPROVED)


def _resolve(resolver, **overrides):
    kwargs = {
        "global_decision": _global_allowed(),
        "portfolio_decision": _portfolio_allowed(),
        "strategy_decision": _strategy_allowed(),
        "execution_decision": _execution_allowed(),
        "venue_decision": _venue_allowed(),
        "risk_result": _approved_risk(),
        "admission_decision": _accepted_admission(),
    }
    kwargs.update(overrides)
    return resolver.resolve(**kwargs)


# ----------------------------------------------------------------------
# 全部放行
# ----------------------------------------------------------------------

def test_all_layers_allowed():
    resolver = EffectiveControlResolver()

    effective = _resolve(resolver)

    assert effective.allow_new_risk
    assert effective.allow_new_orders
    assert effective.allow_reduce_orders
    assert effective.allow_cancel_orders
    assert effective.allow_emergency_flatten


# ----------------------------------------------------------------------
# Global Kill：只关 New Risk / New Order，保留 Risk Reduction
# ----------------------------------------------------------------------

def test_global_kill_blocks_new_orders_but_keeps_risk_reduction():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        global_decision=GlobalControlDecision(
            state=GlobalControlState.KILLED,
            allow_new_risk=False,
            allow_new_orders=False,
            allow_cancel_orders=True,
            allow_reduce_orders=True,
            allow_emergency_flatten=True,
            allow_recovery=True,
            reason="global_killed",
        ),
    )

    assert not effective.allow_new_risk
    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders
    assert effective.allow_cancel_orders
    assert effective.allow_emergency_flatten


# ----------------------------------------------------------------------
# Portfolio：REDUCE_ONLY 不影响 Cancel / Flatten
# ----------------------------------------------------------------------

def test_portfolio_reduce_only_blocks_new_orders_but_keeps_reduce():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        portfolio_decision=PortfolioControlDecision(
            portfolio_id="pf_1",
            current_state=PortfolioState.REDUCE_ONLY,
            allow_new_risk=False,
            allow_new_orders=False,
            allow_reduce_orders=True,
            allow_liquidation=True,
            reason="portfolio_reduce_only",
        ),
    )

    assert not effective.allow_new_risk
    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders


# ----------------------------------------------------------------------
# Risk / Admission 只参与 New Order 路径
# ----------------------------------------------------------------------

def test_risk_rejection_only_gates_new_order_path():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        risk_result=RiskResult(
            decision=RiskDecision.REJECTED,
            reason="limit exceeded",
        ),
    )

    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders
    assert effective.allow_cancel_orders
    assert effective.allow_emergency_flatten


def test_admission_rejection_only_gates_new_order_path():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        admission_decision=OrderAdmissionDecision(
            decision=AdmissionDecision.REJECTED,
            reason=AdmissionReason.CONTROL_BLOCKED,
            request_id=uuid4(),
        ),
    )

    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders


def test_reduce_only_admission_blocks_new_orders():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        admission_decision=OrderAdmissionDecision(
            decision=AdmissionDecision.ACCEPTED_REDUCE_ONLY,
            reason=AdmissionReason.CONTROL_REDUCE_ONLY,
            request_id=uuid4(),
        ),
    )

    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders


def test_missing_risk_and_admission_do_not_restrict():
    """Resolver 未提供 risk / admission 时按放行处理（可仅做控制层合并）。"""
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        risk_result=None,
        admission_decision=None,
    )

    assert effective.allow_new_orders
    assert effective.allow_reduce_orders


# ----------------------------------------------------------------------
# Venue 故障：只影响该 venue，但 reduce 也被阻断
# ----------------------------------------------------------------------

def test_venue_disabled_blocks_new_and_reduce():
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        venue_decision=VenueControlDecision(
            venue="NASDAQ",
            state=VenueState.DISABLED,
            allow_new_orders=False,
            allow_cancel_orders=True,
            allow_reduce_orders=False,
            allow_emergency_flatten=True,
            reason="venue_disabled",
        ),
    )

    assert not effective.allow_new_orders
    assert not effective.allow_reduce_orders
    assert effective.allow_cancel_orders
    assert effective.allow_emergency_flatten


# ----------------------------------------------------------------------
# 多路径联合
# ----------------------------------------------------------------------

def test_new_order_requires_every_layer():
    """New Order 路径是严格的 AND 语义。"""
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        strategy_decision=StrategyControlDecision(
            strategy_id="strat_1",
            current_state=StrategyState.PAUSED,
            allow_signal_generation=False,
            allow_new_orders=False,
            allow_reduce_orders=True,
            reason="strategy_paused",
        ),
    )

    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders


def test_reduce_path_is_independent_of_admission():
    """Reduce 路径不依赖 risk / admission（spec section 23 分开计算）。"""
    resolver = EffectiveControlResolver()

    effective = _resolve(
        resolver,
        risk_result=RiskResult(decision=RiskDecision.REJECTED),
        admission_decision=OrderAdmissionDecision(
            decision=AdmissionDecision.REJECTED,
            reason=AdmissionReason.RISK_REJECTED,
            request_id=uuid4(),
        ),
    )

    assert not effective.allow_new_orders
    assert effective.allow_reduce_orders
    assert effective.allow_cancel_orders
    assert effective.allow_emergency_flatten


def test_reason_aggregates_all_layers():
    resolver = EffectiveControlResolver()

    effective = _resolve(resolver)

    assert "global=global_normal" in effective.reason
    assert "portfolio=portfolio_active" in effective.reason
    assert "strategy=strategy_running" in effective.reason
    assert "execution=execution_active" in effective.reason
    assert "venue=venue_online" in effective.reason
