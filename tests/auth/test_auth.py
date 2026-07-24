from services.auth import *


def test_authentication():


    identity = Identity(

        "001",

        "trader",

        "trader"

    )


    manager = AuthenticationManager(

        TokenService(),

        SessionManager()

    )


    token = manager.login(

        identity

    )


    assert token["user_id"] == "001"