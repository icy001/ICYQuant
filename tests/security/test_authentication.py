"""
Tests for ICYQuant Authentication Service.
"""

import pytest

from services.security.authentication import (
    AuthenticationService,
    AuthProvider,
    TokenType,
    MFAProvider,
    AuthenticationError,
)


class TestAuthenticationService:
    """Test authentication lifecycle management."""

    def test_register_user(self):
        svc = AuthenticationService()
        user = svc.register_user("trader1", "trader1@icyquant.com", password="pass123")
        assert user.username == "trader1"
        assert user.active is True

    def test_register_duplicate_user(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="pass")
        with pytest.raises(AuthenticationError):
            svc.register_user("trader1", "trader1@icyquant.com", password="pass")

    def test_authenticate_user(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="password123")
        session = svc.authenticate("trader1", "password123")
        assert session.user_id is not None
        assert len(session.tokens) == 2

    def test_authenticate_wrong_password(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="password123")
        with pytest.raises(AuthenticationError):
            svc.authenticate("trader1", "wrong_password")

    def test_authenticate_invalid_user(self):
        svc = AuthenticationService()
        with pytest.raises(AuthenticationError):
            svc.authenticate("nonexistent", "password")

    def test_create_service_token(self):
        svc = AuthenticationService()
        token = svc.create_service_token("api_service", scopes={"read", "write"})
        assert token.token_type == TokenType.SERVICE
        assert "read" in token.metadata.get("scopes", [])

    def test_validate_token(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="pass")
        token = svc.create_service_token("test_service")
        validated = svc.validate_token(token.token_value)
        assert validated is not None
        assert validated.token_value == token.token_value

    def test_revoke_token(self):
        svc = AuthenticationService()
        token = svc.create_service_token("test_service")
        svc.revoke_token(token.id)
        validated = svc.validate_token(token.token_value)
        assert validated is None

    def test_refresh_token(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="pass")
        token = svc.create_service_token("test")
        svc._tokens[token.id] = token
        svc._tokens[token.id].token_type = TokenType.REFRESH
        new_token = svc.refresh_token(token.token_value)
        assert new_token is not None

    def test_rate_limiting(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="password123")
        for _ in range(5):
            try:
                svc.authenticate("trader1", "wrong_password")
            except AuthenticationError:
                pass
        with pytest.raises(AuthenticationError):
            svc.authenticate("trader1", "password123")

    def test_end_session(self):
        svc = AuthenticationService()
        svc.register_user("trader1", "trader1@icyquant.com", password="pass")
        session = svc.authenticate("trader1", "pass")
        svc.end_session(session.id)
        assert svc.get_session(session.id) is None

    def test_list_users(self):
        svc = AuthenticationService()
        svc.register_user("user1", "user1@test.com", password="pass")
        svc.register_user("user2", "user2@test.com", password="pass")
        users = svc.list_users()
        assert len(users) == 2

    def test_get_status(self):
        svc = AuthenticationService()
        svc.register_user("user1", "user1@test.com", password="pass")
        status = svc.to_dict()
        assert "users" in status
        assert status["activeSessions"] >= 0
