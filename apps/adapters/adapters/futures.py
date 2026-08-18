"""Futures adapter (CN_FUTURES, CNY) - CTP / Futures Adapter.

Capabilities: submit_order, cancel_order, margin, positions, executions,
settlement. Supports long/short positions, margin, night sessions and
contract multipliers are market-specific; the real gateway depends on the
CTP channel provided by the futures broker.
"""

from __future__ import annotations

from apps.adapters.domain import Capability, Market
from apps.adapters.simulated import SimulatedAdapter


class FuturesAdapter(SimulatedAdapter):
    broker_id = "ctp-demo"
    broker_name = "Simulated CTP Futures"
    adapter_type = "ctp_adapter"
    market = Market.CN_FUTURES
    currency = "CNY"
    slippage = 0.0008
    price_decimals = 2
    margin_rate = 0.12  # 12% initial margin
    capabilities = {
        Capability.SUBMIT_ORDER,
        Capability.CANCEL_ORDER,
        Capability.QUERY_ORDER,
        Capability.POSITIONS,
        Capability.EXECUTIONS,
        Capability.ACCOUNT_BALANCE,
        Capability.MARGIN,
        Capability.SETTLEMENT,
    }

    def __init__(self) -> None:
        super().__init__(
            accounts={
                "futures_main": ("Futures Main", 500_000.0, 400_000.0),
            },
            price_book={
                "IF2609": 4010.0,  # 沪深300股指期货
                "rb2610": 3085.0,  # 螺纹钢
                "au2612": 588.0,  # 沪金
            },
            seed_positions={
                "futures_main": [
                    {"symbol": "IF2609", "side": "BUY", "quantity": 2,
                     "average_price": 3980.0, "last_price": 4010.0},
                    {"symbol": "rb2610", "side": "SELL", "quantity": 10,
                     "average_price": 3100.0, "last_price": 3085.0},
                    {"symbol": "au2612", "side": "BUY", "quantity": 4,
                     "average_price": 585.0, "last_price": 588.0},
                ],
            },
            seed_orders={
                "futures_main": [
                    {"order_id": "ORD-CN_FUTURES-000001", "symbol": "IF2609",
                     "side": "BUY", "quantity": 1, "price": 4008.0,
                     "status": "ACCEPTED"},
                ],
            },
            seed_executions={
                "futures_main": [
                    {"execution_id": "EXEC-CN_FUTURES-000001",
                     "order_id": "ORD-CN_FUTURES-SEED1", "symbol": "IF2609",
                     "side": "BUY", "fill_quantity": 2, "fill_price": 3980.0},
                ],
            },
        )
