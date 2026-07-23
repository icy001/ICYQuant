"""
Prompt template model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:

    template_id: str

    name: str

    content: str