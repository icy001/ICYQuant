"""
Prompt variable definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptVariable:

    name: str

    default_value: str

    required: bool = True