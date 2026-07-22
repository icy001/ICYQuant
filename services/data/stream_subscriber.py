"""
Streaming subscriber interface.
"""

from abc import ABC, abstractmethod


class StreamSubscriber(ABC):

    @abstractmethod
    def on_tick(
        self,
        tick,
    ):

        """Receive tick."""