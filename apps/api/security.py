"""
API authentication helpers.
"""

from fastapi import (
    Header,
    HTTPException,
)

from services.security import (
    JWTService,
)


jwt_service = JWTService(
    "icyquant-secret"
)


def authenticate(
    authorization:
    str = Header()
):
    if not authorization.startswith(
        "Bearer "
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    token = (
        authorization
        .replace(
            "Bearer ",
            ""
        )
    )

    return jwt_service.decode(
        token
    )