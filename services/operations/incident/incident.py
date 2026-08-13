"""Incident model (Commit 27 Part 1.4, spec sections 9-10, 16-17).

Incident 必须区分 Symptom 与 Root Cause：

    Symptoms:
        Risk unavailable
        OMS unavailable
        Position stale

    Root Cause:
        event-bus connection failure

Root Cause 是审计信息，不允许把推测当事实自动写入；
模型允许 root_cause = None，直到人工或确定性的诊断逻辑确认。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .severity import IncidentSeverity
from .state import IncidentState
from .impact import IncidentImpact
from .context import IncidentContext


@dataclass
class Incident:

    context: IncidentContext

    title: str

    description: str

    severity: IncidentSeverity

    state: IncidentState

    impact: IncidentImpact

    root_cause: str | None = None

    assigned_to: str | None = None

    resolved_at: datetime | None = None

    closed_at: datetime | None = None
