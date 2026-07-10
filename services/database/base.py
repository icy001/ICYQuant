"""
SQLAlchemy declarative base.

All ORM models inherit from Base.
"""

from __future__ import annotations

from sqlalchemy.orm import (
    DeclarativeBase,
)


class Base(
    DeclarativeBase
):
    """
    ICYQuant ORM Base.

    Every database model
    should inherit this class.
    """

    pass