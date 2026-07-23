"""
Agent communication message.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AgentMessage:

    sender: str

    receiver: str

    topic: str

    payload: Any

    timestamp: datetime