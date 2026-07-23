"""
LLM provider interface.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def complete(
        self,
        messages,
    ):
        """Generate completion."""