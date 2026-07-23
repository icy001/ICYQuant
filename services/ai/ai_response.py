"""
AI response model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AIResponse:

    request_id: str

    content: str

    metadata: dict