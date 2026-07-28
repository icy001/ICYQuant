from dataclasses import dataclass


@dataclass
class Node:
    node_id: str
    state: str
    term: int
