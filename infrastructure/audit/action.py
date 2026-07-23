"""
Auditable action.
"""


from dataclasses import dataclass


@dataclass
class Action:

    name: str

    resource: str