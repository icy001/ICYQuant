"""
Portfolio query response.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResponse:

    success: bool

    data: dict