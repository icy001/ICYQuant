from services.ledger.entry import LedgerEntry
from services.ledger.transaction import Transaction
from services.ledger.account import LedgerDirection
from services.ledger.transaction_repository import TransactionRepository
from services.ledger.manager import LedgerManager
from services.ledger.transaction_service import LedgerService


def test_ledger_service():
    repository = TransactionRepository()

    manager = LedgerManager(repository)

    service = LedgerService(manager)

    entry = LedgerEntry(
        "ENTRY001",
        "ACC001",
        10000,
        "USD",
        LedgerDirection.CREDIT
    )

    transaction = Transaction(
        "TX001",
        "Deposit",
        [
            entry
        ]
    )

    result = service.post(transaction)

    assert result.transaction_id == "TX001"