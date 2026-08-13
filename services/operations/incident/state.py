"""Incident state machine (Commit 27 Part 1.4, spec sections 4-5, 28-29).

Incident 生命周期必须是 Deterministic State Machine，而不是几个字符串字段随便改:

    DETECTED
       ↓
    TRIAGED
       ↓
    INVESTIGATING
       ↓
    MITIGATING
       ↓
    RECOVERING
       ↓
    MONITORING
       ↓
    RESOLVED
       ↓
    CLOSED

不允许 CLOSED → INVESTIGATING，也不允许 DETECTED → RESOLVED。
"""

from enum import Enum


class IncidentState(str, Enum):

    DETECTED = "DETECTED"

    TRIAGED = "TRIAGED"

    INVESTIGATING = "INVESTIGATING"

    MITIGATING = "MITIGATING"

    RECOVERING = "RECOVERING"

    MONITORING = "MONITORING"

    RESOLVED = "RESOLVED"

    CLOSED = "CLOSED"


VALID_TRANSITIONS = {
    IncidentState.DETECTED: {
        IncidentState.TRIAGED,
    },
    IncidentState.TRIAGED: {
        IncidentState.INVESTIGATING,
        IncidentState.MITIGATING,
    },
    IncidentState.INVESTIGATING: {
        IncidentState.MITIGATING,
    },
    IncidentState.MITIGATING: {
        IncidentState.RECOVERING,
    },
    IncidentState.RECOVERING: {
        IncidentState.MONITORING,
    },
    IncidentState.MONITORING: {
        IncidentState.RESOLVED,
    },
    IncidentState.RESOLVED: {
        IncidentState.CLOSED,
    },
    IncidentState.CLOSED: set(),
}


def transition(incident, target_state):
    """执行一次合法的状态迁移，返回迁移前的状态。

    非法的迁移（例如 DETECTED -> RESOLVED、CLOSED -> INVESTIGATING）
    会抛出 ValueError，且不会修改 incident.state。
    """

    allowed = VALID_TRANSITIONS.get(
        incident.state,
        set(),
    )

    if target_state not in allowed:
        raise ValueError(
            f"invalid transition: "
            f"{incident.state} -> "
            f"{target_state}"
        )

    previous = incident.state

    incident.state = target_state

    return previous
