from services.ledger.models.entry import LedgerEntry


class LedgerService:
    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    def get_all(self, user_id: str) -> list[LedgerEntry]:
        return [entry for entry in self.entries if entry.user_id == user_id]
