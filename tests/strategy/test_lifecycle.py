from services.strategy.lifecycle import (
    StrategyState,
    StrategyRecord,
    StrategyLifecycleManager,
    StrategyGovernance,
)
from services.strategy.lifecycle.transition import (
    TransitionValidator,
)


def test_activate_strategy():
    strategy = StrategyRecord(
        strategy_id="momentum",
        version="1.0",
        state=StrategyState.PAPER,
        allocation=0.1,
    )

    manager = StrategyLifecycleManager(
        TransitionValidator(),
    )

    result = manager.transition(
        strategy,
        StrategyState.LIVE,
    )

    assert result.success is True
    assert strategy.state == StrategyState.LIVE


def test_invalid_transition():
    strategy = StrategyRecord(
        strategy_id="momentum",
        version="1.0",
        state=StrategyState.CREATED,
        allocation=0.1,
    )

    manager = StrategyLifecycleManager(
        TransitionValidator(),
    )

    result = manager.transition(
        strategy,
        StrategyState.LIVE,
    )

    assert result.success is False
    assert result.reason == "INVALID_TRANSITION"


def test_governance_degrade():
    governance = StrategyGovernance()

    result = governance.evaluate(
        sharpe=0.3,
        drawdown=0.1,
    )

    assert result == "DEGRADE"


def test_governance_suspend():
    governance = StrategyGovernance()

    result = governance.evaluate(
        sharpe=1.5,
        drawdown=0.25,
    )

    assert result == "SUSPEND"


def test_governance_keep():
    governance = StrategyGovernance()

    result = governance.evaluate(
        sharpe=2.0,
        drawdown=0.1,
    )

    assert result == "KEEP"


def test_transition_paper_to_live():
    strategy = StrategyRecord(
        strategy_id="demo",
        version="1.0",
        state=StrategyState.PAPER,
        allocation=0.2,
    )

    manager = StrategyLifecycleManager(
        TransitionValidator(),
    )

    result = manager.transition(strategy, StrategyState.LIVE)

    assert result.success is True
    assert result.new_state == "LIVE"