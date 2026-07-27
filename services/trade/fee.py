from dataclasses import dataclass


@dataclass
class TradeFee:
    trade_id: str
    commission: float
    exchange_fee: float