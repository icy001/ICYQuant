from infrastructure.secrets import *


def test_secret():

    vault = SecretVault()

    vault.save(

        Secret(

            "api",

            "123"

        )

    )

    assert vault.get(

        "api"

    ).value == "123"