from services.secret import *


def test_secret_service():
    service = SecretService(
        SecretManager(
            SecretRepository(),
            EncryptionService()
        )
    )

    secret = Secret(
        "SEC001",
        "BROKER_KEY",
        "ABC123",
        SecretType.API_KEY
    )

    service.save(secret)

    result = service.get("SEC001")

    assert result.value == "ABC123"