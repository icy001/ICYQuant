"""
RootCause — structured root-cause analysis.

A postmortem is not a free-text essay: the root cause is categorised and
carries supporting detail, contributing factors and a confidence score
(spec section 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class RootCauseCategory(str, Enum):
    CODE = "CODE"
    CONFIGURATION = "CONFIGURATION"
    DATA = "DATA"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    EXTERNAL = "EXTERNAL"
    HUMAN = "HUMAN"
    PROCESS = "PROCESS"
    UNKNOWN = "UNKNOWN"


@dataclass
class RootCause:

    category: RootCauseCategory
    summary: str

    technical_detail: str = ""
    contributing_factors: Optional[List[str]] = None
    confidence: float = 0.0
