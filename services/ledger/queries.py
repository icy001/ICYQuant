"""
Ledger query objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JournalQuery:
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    account_code: Optional[str] = None