"""
AI Provider abstraction.
"""

from abc import ABC, abstractmethod


class AIProvider(ABC):

    @abstractmethod
    def generate(
        self,
        prompt: str,
    ):
        """Generate AI response."""