"""
Cluster node model.
"""

from dataclasses import dataclass


@dataclass
class ClusterNode:

    node_id: str

    address: str

    role: str

    alive: bool = True