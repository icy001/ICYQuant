"""
Backtest event queue.
"""

from collections import deque


class EventQueue:
    def __init__(self):
        self._queue = deque()

    def push(
        self,
        event,
    ):
        self._queue.append(event)

    def pop(self):
        return self._queue.popleft()