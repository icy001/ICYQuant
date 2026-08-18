"""A-Share broker adapter (CN_STOCK, CNY).

Capabilities: submit_order, cancel_order, positions, executions,
account_balance. Programmatic trading permissions and the real order
channel always depend on the broker's open API and regulatory rules;
this simulated adapter implements the unified contract for testing and
the Dashboard.
"""

from __future__ import annotations

from apps.adapters.domain import Capability, Market
from apps.adapters.simulated import SimulatedAdapter


class AshareAdapter(SimulatedAdapter):
    broker_id = "cnbroker-demo"
    broker_name = "Simulated A-Share Broker"
    adapter_type = "broker_adapter"
    market = Market.CN_STOCK
    currency = "CNY"
    slippage = 0.001
    price_decimals = 2
    capabilities = {
        Capability.SUBMIT_ORDER,
        Capability.CANCEL_ORDER,
        Capability.QUERY_ORDER,
        Capability.POSITIONS,
        Capability.EXECUTIONS,
        Capability.ACCOUNT_BALANCE,
    }

    def __init__(self) -> None:
        super().__init__(
            accounts={
                "ashare_main": ("A-Share Main", 1_000_000.0, 800_000.0),
            },
            price_book={
                "600519": 1520.00,  # 贵州茅台
                "000001": 11.40,  # 平安银行
                "510300": 3.90,  # 沪深300ETF
            },
            seed_positions={
                "ashare_main": [
                    {"symbol": "600519", "side": "BUY", "quantity": 100,
                     "average_price": 1500.0, "last_price": 1520.0},
                    {"symbol": "000001", "side": "BUY", "quantity": 5000,
                     "average_price": 11.2, "last_price": 11.4},
                    {"symbol": "510300", "side": "BUY", "quantity": 20000,
                     "average_price": 3.85, "last_price": 3.9},
                ],
            },
            seed_orders={
                "ashare_main": [
                    {"order_id": "ORD-CN_STOCK-000001", "symbol": "600519",
                     "side": "BUY", "quantity": 100, "price": 1518.0,
                     "status": "ACCEPTED"},
                ],
            },
            seed_executions={
                "ashare_main": [
                    {"execution_id": "EXEC-CN_STOCK-000001", "order_id": "ORD-CN_STOCK-SEED1",
                     "symbol": "600519", "side": "BUY", "fill_quantity": 100,
                     "fill_price": 1500.0},
                ],
            },
        )
