from dataclasses import dataclass


@dataclass
class Fill:
    symbol: str
    quantity: int
    price: float


class SimulatedBroker:
    def execute(
        self,
        signal,
        price
    ):
        if signal.signal_type.value == "BUY":
            return Fill(
                symbol=signal.symbol,
                quantity=100,
                price=price
            )
        return None