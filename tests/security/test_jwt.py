from services.security import (
    JWTService,
)


def test_jwt():
    service = JWTService(
        "secret"
    )

    token = service.create_token(
        "user001",
        "TRADER"
    )

    payload = service.decode(
        token
    )

    assert (
        payload["role"]
        ==
        "TRADER"
    )