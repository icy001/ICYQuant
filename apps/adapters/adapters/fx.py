"""FX adapter (FX, USD account currency).

Capabilities: submit_order, cancel_order, positions, margin,
account_balance, leverage, swap. Real connectivity may use Broker API,
MT5 or FIX; the concrete channel is decided by the actual broker. This
simulated adapter implements the unified contract for testing and the
Dashboard.
"""

from __future__ import annotations

from apps.adapters.domain import Capability, Market
from apps.adapters.simulated import SimulatedAdapter


class FxAdapter(SimulatedAdapter):
    broker_id = "fx-demo"
    broker_name = "Simulated FX Broker"
    adapter_type = "fx_broker_adapter"
    market = Market.FX
    currency = "USD"
    slippage = 0.0002
    price_decimals = 5
    leverage = 30.0  # 1:30
    capabilities = {
        Capability.SUBMIT_ORDER,
        Capability.CANCEL_ORDER,
        Capability.QUERY_ORDER,
        Capability.POSITIONS,
        Capability.EXECUTIONS,
        Capability.ACCOUNT_BALANCE,
        Capability.MARGIN,
        Capability.LEVERAGE,
        Capability.SWAP,
    }

    def __init__(self) -> None:
        super().__init__(
            accounts={
                "fx_main": ("FX Main", 120_000.0, 90_000.0),
            },
            price_book={
                "EURUSD": 1.08700,
                "GBPUSD": 1.26200,
                "USDJPY": 149.500,
            },
            seed_positions={
                "fx_main": [
                    {"symbol": "EURUSD", "side": "BUY", "quantity": 100000,
                     "average_price": 1.08500, "last_price": 1.08700},
                    {"symbol": "GBPUSD", "side": "SELL", "quantity": 50000,
                     "average_price": 1.26500, "last_price": 1.26200},
                ],
            },
            seed_orders={
                "fx_main": [
                    {"order_id": "ORD-FX-000001", "symbol": "EURUSD",
                     "side": "BUY", "quantity": 10000, "price": 1.08750,
                     "status": "ACCEPTED"},
                ],
            },
            seed_executions={
                "fx_main": [
                    {"execution_id": "EXEC-FX-000001", "order_id": "ORD-FX-SEED1",
                     "symbol": "EURUSD", "side": "BUY", "fill_quantity": 100000,
                     "fill_price": 1.08500},
                ],
            },
        )
