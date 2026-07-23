"""
Audit actor.
"""


from dataclasses import dataclass


@dataclass
class Actor:

    id: str

    type: str