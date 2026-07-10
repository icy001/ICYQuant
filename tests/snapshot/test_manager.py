from decimal import Decimal
from uuid import uuid4

from services.projection import (
    PortfolioState,
    PositionProjection,
    CashProjection,
)

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)

from services.snapshot import (
    SnapshotManager,
)


def test_snapshot_manager_create():
    state = PortfolioState()
    
    deposit = LedgerEvent(
        event_type=LedgerEventType.CASH_DEPOSITED,
        payload={"currency": "USD", "amount": 100000}
    )
    
    CashProjection(state).apply(deposit)
    
    manager = SnapshotManager()
    event_id = uuid4()
    
    snapshot = manager.create(state, event_id)
    
    assert snapshot.snapshot_id is not None
    assert snapshot.event_id == event_id
    assert snapshot.state["cash"]["USD"]["balance"] == "100000"


def test_snapshot_manager_serialize():
    state = PortfolioState()
    
    position = state.get_position("NVDA")
    position.quantity = Decimal("100")
    position.average_price = Decimal("150.5")
    
    state.cash["USD"] = type('CashState', (), {'balance': Decimal("50000")})
    
    manager = SnapshotManager()
    
    serialized = manager.serialize(state)
    
    assert serialized["positions"]["NVDA"]["quantity"] == "100"
    assert serialized["positions"]["NVDA"]["average_price"] == "150.5"