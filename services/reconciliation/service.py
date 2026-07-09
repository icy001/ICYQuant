from .comparator import ReconciliationComparator


class ReconciliationService:
    def __init__(self) -> None:
        self.comparator = ReconciliationComparator()

    def reconcile(
        self,
        ledger,
        position,
    ):
        return self.comparator.compare(ledger, position)
