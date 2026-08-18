"""US Equity adapter (US_EQUITY, USD) - e.g. 盈立 / Yuanta Global.

Capabilities: submit_order, cancel_order, positions, executions,
buying_power. The concrete access path (OpenAPI / Broker API) always
depends on what the actual account grants; this simulated adapter
implements the unified contract for testing and the Dashboard.
"""

from __future__ import annotations

from apps.adapters.domain import Capability, Market
from apps.adapters.simulated import SimulatedAdapter


class UsEquityAdapter(SimulatedAdapter):
    broker_id = "yl-global"
    broker_name = "Yuanta Global (US)"
    adapter_type = "us_broker_adapter"
    market = Market.US_EQUITY
    currency = "USD"
    slippage = 0.0005
    price_decimals = 2
    capabilities = {
        Capability.SUBMIT_ORDER,
        Capability.CANCEL_ORDER,
        Capability.QUERY_ORDER,
        Capability.POSITIONS,
        Capability.EXECUTIONS,
        Capability.ACCOUNT_BALANCE,
        Capability.BUYING_POWER,
    }

    def __init__(self) -> None:
        super().__init__(
            accounts={
                "us_main": ("US Equity Main", 250_000.0, 150_000.0),
            },
            price_book={
                "AAPL": 178.50,
                "MSFT": 316.00,
                "NVDA": 122.00,
            },
            seed_positions={
                "us_main": [
                    {"symbol": "AAPL", "side": "BUY", "quantity": 200,
                     "average_price": 175.0, "last_price": 178.5},
                    {"symbol": "MSFT", "side": "BUY", "quantity": 150,
                     "average_price": 310.0, "last_price": 316.0},
                    {"symbol": "NVDA", "side": "BUY", "quantity": 100,
                     "average_price": 118.0, "last_price": 122.0},
                ],
            },
            seed_orders={
                "us_main": [
                    {"order_id": "ORD-US_EQUITY-000001", "symbol": "AAPL",
                     "side": "BUY", "quantity": 10, "price": 178.0,
                     "status": "ACCEPTED"},
                ],
            },
            seed_executions={
                "us_main": [
                    {"execution_id": "EXEC-US_EQUITY-000001",
                     "order_id": "ORD-US_EQUITY-SEED1", "symbol": "AAPL",
                     "side": "BUY", "fill_quantity": 200, "fill_price": 175.0},
                ],
            },
        )
