"""
Portfolio query request.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryRequest:

    query_id: str

    portfolio_id: str

    query_type: str