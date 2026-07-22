"""
Workspace member.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceMember:

    user_id: str

    team_id: str

    role: str