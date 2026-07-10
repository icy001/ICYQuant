from dataclasses import dataclass


@dataclass(frozen=True)
class Universe:
    symbols: list[str]

    def contains(self, symbol: str) -> bool:
        return symbol in self.symbols

    def __len__(self) -> int:
        return len(self.symbols)

    def __iter__(self):
        return iter(self.symbols)