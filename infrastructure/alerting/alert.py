"""
Alert model.
"""


from dataclasses import dataclass


@dataclass
class Alert:

    name: str

    message: str

    severity: str

    source: str