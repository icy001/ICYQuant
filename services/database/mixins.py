"""
Reusable SQLAlchemy model mixins.
"""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Boolean,
    Uuid,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )