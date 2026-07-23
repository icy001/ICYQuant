"""
Experience replay memory.
"""

from collections import deque


class ExperienceReplayMemory:

    def __init__(
        self,
        capacity=100000,
    ):

        self.buffer = deque(
            maxlen=capacity
        )

    def add(
        self,
        experience,
    ):

        self.buffer.append(
            experience
        )

    def sample(
        self,
        batch_size,
    ):

        return list(
            self.buffer
        )[:batch_size]

    def size(self):

        return len(
            self.buffer
        )