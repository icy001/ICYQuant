from dataclasses import dataclass


@dataclass
class Query:
    query_id: str
    query_type: str
    params: dict
