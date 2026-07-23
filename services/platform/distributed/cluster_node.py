"""
Cluster node model.
"""

from dataclasses import dataclass


@dataclass
class ClusterNode:

    node_id: str

    hostname: str

    cpu_usage: float

    memory_usage: float

    status: str