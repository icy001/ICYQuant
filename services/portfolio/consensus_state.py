"""
Consensus state.
"""

from enum import Enum


class ConsensusState(Enum):

    FOLLOWER = "FOLLOWER"

    CANDIDATE = "CANDIDATE"

    LEADER = "LEADER"