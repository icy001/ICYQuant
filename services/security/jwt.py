"""
JWT token service.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import jwt


class JWTService:
    def __init__(
        self,
        secret: str,
    ):
        self.secret = secret

    def create_token(
        self,
        user_id: str,
        role: str,
    ):
        payload = {
            "sub":
            user_id,
            "role":
            role,
            "exp":
            datetime.utcnow()
            +
            timedelta(
                hours=8
            )
        }

        return jwt.encode(
            payload,
            self.secret,
            algorithm="HS256"
        )

    def decode(
        self,
        token: str,
    ):
        return jwt.decode(
            token,
            self.secret,
            algorithms=[
                "HS256"
            ]
        )