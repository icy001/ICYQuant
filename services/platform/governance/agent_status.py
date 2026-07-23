"""
Agent lifecycle status.
"""

from enum import Enum


class AgentStatus(Enum):

    CREATED = "created"

    STARTING = "starting"

    RUNNING = "running"

    DEGRADED = "degraded"

    STOPPING = "stopping"

    STOPPED = "stopped"

    FAILED = "failed"