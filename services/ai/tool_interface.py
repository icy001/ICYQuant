"""
Unified AI tool interface.
"""

from abc import ABC, abstractmethod


class AITool(ABC):

    @property
    @abstractmethod
    def name(self):

        pass

    @abstractmethod
    def execute(
        self,
        arguments: dict,
    ):

        pass