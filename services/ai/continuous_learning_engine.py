"""
Continuous learning engine.
"""


class ContinuousLearningEngine:

    def __init__(
        self,
        replay_memory,
    ):

        self.replay_memory = replay_memory

    def learn(
        self,
        experience,
    ):

        self.replay_memory.add(
            experience
        )

        return {
            "status": "accepted",
            "memory_size": self.replay_memory.size(),
        }