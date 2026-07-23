"""
Agent tool definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:

    name: str

    description: str

    parameters: dict