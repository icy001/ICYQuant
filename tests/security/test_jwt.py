"""
Tests for ICYQuant JWT/Token management.
"""

from services.security.token_manager import TokenManager, TokenConfig


def test_jwt():
    config = TokenConfig(
        issuer="icyquant",
        audience="icyquant-services",
        expiration_minutes=60,
    )
    service = TokenManager(config)

    token = service.create_token("user001", roles=["TRADER"])
    validation = service.validate_token(token)

    assert validation.valid is True
    assert validation.claims.subject == "user001"
    assert "TRADER" in validation.claims.roles
