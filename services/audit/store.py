"""
Audit store abstraction.
"""

from __future__ import annotations

from typing import Protocol

from .model import AuditRecord


class AuditStore(Protocol):
    def append(
        self,
        record: AuditRecord,
    ) -> None:
        ...

    def list_all(
        self,
    ) -> list[AuditRecord]:
        ...