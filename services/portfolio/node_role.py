"""
Cluster node role.
"""

from enum import Enum


class NodeRole(Enum):

    LEADER = "LEADER"

    FOLLOWER = "FOLLOWER"

    STANDBY = "STANDBY"