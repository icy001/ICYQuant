from decimal import Decimal

import pytest

from services.portfolio import (
    CashAccount,
    CashTransaction,
    CashManagementEngine,
    CashRepository,
    CashService,
    CashSnapshot,
)


def test_cash_deposit():
    engine = CashManagementEngine()

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("0"),
    )

    engine.deposit(account, Decimal("500"))

    assert account.balance == Decimal("1500")


def test_cash_withdraw():
    engine = CashManagementEngine()

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("0"),
    )

    engine.withdraw(account, Decimal("300"))

    assert account.balance == Decimal("700")


def test_cash_withdraw_insufficient():
    engine = CashManagementEngine()

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("500"),
    )

    with pytest.raises(ValueError, match="insufficient cash"):
        engine.withdraw(account, Decimal("600"))


def test_cash_reserve():
    engine = CashManagementEngine()

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("0"),
    )

    engine.reserve(account, Decimal("200"))

    assert account.reserved == Decimal("200")


def test_cash_available():
    engine = CashManagementEngine()

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("200"),
    )

    available = engine.available(account)

    assert available == Decimal("800")


def test_cash_transaction():
    transaction = CashTransaction(
        transaction_id="txn-001",
        amount=Decimal("500"),
        transaction_type="DEPOSIT",
    )

    assert transaction.transaction_id == "txn-001"
    assert transaction.amount == Decimal("500")
    assert transaction.transaction_type == "DEPOSIT"


def test_cash_repository():
    repo = CashRepository()
    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("0"),
    )

    repo.save(account)
    retrieved = repo.get("USD")

    assert retrieved is not None
    assert retrieved.currency == "USD"


def test_cash_service():
    engine = CashManagementEngine()
    repo = CashRepository()
    service = CashService(engine, repo)

    account = CashAccount(
        currency="USD",
        balance=Decimal("1000"),
        reserved=Decimal("0"),
    )
    repo.save(account)

    updated = service.deposit("USD", Decimal("500"))

    assert updated.balance == Decimal("1500")


def test_cash_snapshot():
    snapshot = CashSnapshot(
        currency="USD",
        balance=Decimal("1000"),
        available=Decimal("800"),
    )

    assert snapshot.currency == "USD"
    assert snapshot.balance == Decimal("1000")
    assert snapshot.available == Decimal("800")