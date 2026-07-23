"""
AI model definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AIModel:

    model_id: str

    provider: str

    version: str

    context_window: int