"""
Database session utilities.
"""

from __future__ import annotations

from .connection import (
    SessionLocal,
)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()