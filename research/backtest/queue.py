from queue import Queue
from typing import Optional

from .event import Event


class EventQueue:
    def __init__(self):
        self._queue = Queue()

    def publish(self, event: Event) -> None:
        self._queue.put(event)

    def get(self) -> Event:
        return self._queue.get()

    def peek(self) -> Optional[Event]:
        if not self._queue.empty():
            return self._queue.queue[0]
        return None

    def empty(self) -> bool:
        return self._queue.empty()

    def size(self) -> int:
        return self._queue.qsize()