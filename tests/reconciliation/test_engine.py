from decimal import Decimal

from services.projection import (
    PortfolioState,
    PositionState,
)

from services.reconciliation import (
    ReconciliationEngine,
)


def test_reconciliation_engine():
    state = PortfolioState()

    state.positions["NVDA"] = PositionState(
        symbol="NVDA",
        quantity=Decimal("100")
    )

    engine = ReconciliationEngine()

    differences = engine.reconcile_positions(
        state,
        {"NVDA": Decimal("90")}
    )

    assert len(differences) == 1
    assert differences[0].symbol == "NVDA"