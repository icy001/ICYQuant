"""
Tool execution result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:

    tool_name: str

    success: bool

    data: object

    metadata: dict