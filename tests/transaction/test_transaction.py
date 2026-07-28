from services.transaction import *


def test_transaction():

    service = TransactionService(
        TransactionRepository()
    )

    tx = Transaction(
        "TX001",
        TransactionState.CREATED,
        "ORDER"
    )

    result = service.begin(tx)

    assert result.status == "CONFIRMED"
