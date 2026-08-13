"""Governance domain model — Principal (Commit 28 Part 1.1).

Principal 回答"谁？"。支持 USER / SERVICE / SYSTEM / BOT 等主体类型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """A governance actor: human, service, system, or automation."""

    principal_id: str
    name: str
    principal_type: str
    active: bool = True
