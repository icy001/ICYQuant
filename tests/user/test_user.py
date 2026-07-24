from services.user import *


def test_user_service():


    repository = UserRepository()


    manager = UserManager(

        repository

    )


    service = UserService(

        manager

    )


    user = User(

        "001",

        "quant",

        "quant@test.com"

    )


    service.register(user)


    result = service.profile(

        "001"

    )


    assert result.username == "quant"