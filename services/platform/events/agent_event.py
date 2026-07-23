"""
Agent Event.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AgentEvent:

    event_id: str

    event_type: str

    source: str

    payload: Any

    created_at: datetime