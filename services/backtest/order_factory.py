"""
Signal to virtual order mapper.
"""


class VirtualOrderFactory:
    def create(
        self,
        signal,
    ):
        return {
            "symbol": signal.symbol,
            "side": signal.side,
            "quantity": signal.quantity,
        }