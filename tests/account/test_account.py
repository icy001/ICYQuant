from services.account import *


def test_account_service():


    repository = AccountRepository()


    manager = AccountManager(

        repository

    )


    service = AccountService(

        manager

    )


    account = Account(

        "ACC001",

        "USER001",

        AccountType.TRADING

    )


    service.open_account(account)


    result = service.query_account(

        "ACC001"

    )


    assert result.account_id == "ACC001"