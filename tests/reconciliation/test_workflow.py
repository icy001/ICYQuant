from decimal import Decimal

from services.ledger import (
    MemoryEventStore,
    LedgerRepository,
)

from services.projection import (
    PortfolioState,
    ProjectionEngine,
)

from services.reconciliation import (
    ReconciliationWorkflow,
)


def test_auto_repair():
    repository = LedgerRepository(
        MemoryEventStore()
    )

    engine = ProjectionEngine([])

    workflow = ReconciliationWorkflow(
        repository,
        engine
    )

    state = PortfolioState()

    from services.projection import PositionState
    state.positions["NVDA"] = PositionState(
        symbol="NVDA",
        quantity=Decimal("100")
    )

    repairs = workflow.execute(
        state,
        {
            "NVDA":
                Decimal("100")
        }
    )

    assert len(repairs) == 0