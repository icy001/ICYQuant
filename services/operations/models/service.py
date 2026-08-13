"""
Service identity model (Commit 27 Part 1.1, spec sections 4-5).

生产环境可能存在 risk-service 的多个实例：

    risk-service
        ├── instance-01
        ├── instance-02
        └── instance-03

不能只知道 "Risk Service = DOWN"，还必须知道：
service_id / instance_id / version / environment，
后续排查 "为什么只有 instance-02 出问题" 才有依据。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ServiceState(str, Enum):

    STARTING = "STARTING"

    HEALTHY = "HEALTHY"

    DEGRADED = "DEGRADED"

    UNHEALTHY = "UNHEALTHY"

    STOPPED = "STOPPED"

    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ServiceIdentity:

    service_id: str

    name: str

    version: str

    environment: str

    instance_id: str
