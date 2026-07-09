import json
from typing import Dict, List


class EventStream:
    def __init__(self):
        self.subscribers = []
        self.events = []

    def subscribe(self, callback) -> None:
        self.subscribers.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def publish(self, event_type: str, data: Dict) -> None:
        event = {
            "type": event_type,
            "data": data,
        }
        self.events.append(event)

        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception:
                pass

    def get_events(self, limit: int = 100) -> List:
        return self.events[-limit:]

    def clear(self) -> None:
        self.events = []


class WebSocketEventHandler:
    def __init__(self, stream: EventStream):
        self.stream = stream

    def on_order_update(self, order) -> None:
        self.stream.publish("ORDER_UPDATE", {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "status": order.status.value,
            "side": order.side,
            "quantity": order.quantity,
        })

    def on_trade_fill(self, fill) -> None:
        self.stream.publish("TRADE_FILL", {
            "order_id": fill.order_id,
            "symbol": fill.symbol,
            "quantity": fill.quantity,
            "price": fill.price,
        })

    def on_risk_update(self, dashboard) -> None:
        self.stream.publish("RISK_UPDATE", dashboard.to_dict())

    def on_position_update(self, portfolio) -> None:
        self.stream.publish("POSITION_UPDATE", portfolio.to_dict())