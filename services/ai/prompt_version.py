"""
Prompt version model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PromptVersion:

    prompt_id: str

    version: str

    content: str

    created_at: datetime