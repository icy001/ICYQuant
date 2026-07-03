from services.common.event_bus import EventBus
from services.common.events.order_event import Event, EventType


class PositionService:
    def __init__(self, bus: EventBus) -> None:
        self.positions: dict[str, float] = {}
        self.bus = bus
        self.bus.subscribe(EventType.TRADE_EXECUTED, self.on_trade)

    def on_trade(self, event: Event) -> None:
        symbol = str(event.payload.get("symbol", event.order_id))
        quantity = float(event.payload.get("qty", 0))
        side = str(event.payload.get("side", "BUY")).upper()
        signed_quantity = quantity if side == "BUY" else -quantity
        self.positions[symbol] = self.positions.get(symbol, 0.0) + signed_quantity
