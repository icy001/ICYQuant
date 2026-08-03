"""Common type definitions."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import uuid4

T = TypeVar("T")

def generate_id(prefix: str = "") -> str:
    return f"{prefix}{uuid4().hex}"

@dataclass
class Timestamp:
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()

@dataclass
class Pagination:
    page: int = 1
    page_size: int = 100
    total: int = 0

@dataclass
class SortOrder:
    field: str = ""
    direction: str = "asc"

@dataclass
class Metadata:
    id: str = field(default_factory=lambda: generate_id())
    tags: Dict[str, str] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)

JsonDict = Dict[str, Any]
JsonList = List[Any]
JsonValue = Union[str, int, float, bool, None, JsonDict, JsonList]
