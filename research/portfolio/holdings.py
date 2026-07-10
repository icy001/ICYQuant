from typing import Dict

from .position import Position


class Holdings:
    def __init__(self):
        self.positions: Dict[str, Position] = {}

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]