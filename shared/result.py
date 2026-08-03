"""Unified Result type for all operations."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Generic, List, Optional, TypeVar

from shared.exceptions import ICYQuantError

T = TypeVar("T")

@dataclass
class Result(Generic[T]):
    """Generic result type for operations that may succeed or fail."""
    success: bool
    data: Optional[T] = None
    error: Optional[ICYQuantError] = None
    warnings: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: T = None, warnings: Optional[List[str]] = None, **metadata: Any) -> Result[T]:
        return cls(success=True, data=data, warnings=warnings or [], metadata=metadata)

    @classmethod
    def fail(cls, error: ICYQuantError, data: Optional[T] = None, **metadata: Any) -> Result[T]:
        return cls(success=False, data=data, error=error, metadata=metadata)

    @property
    def failed(self) -> bool:
        return not self.success

    @property
    def error_code(self) -> int:
        return self.error.error_code if self.error else 0

    @property
    def error_message(self) -> str:
        return self.error.message if self.error else ""

    def unwrap(self) -> T:
        if self.failed:
            raise self.error
        return self.data

    def unwrap_or(self, default: T = None) -> T:
        return self.data if self.success else default

    def map(self, func) -> Result:
        if self.success and self.data is not None:
            try:
                return Result.ok(func(self.data), warnings=self.warnings, **self.metadata)
            except ICYQuantError as e:
                return Result.fail(e, data=self.data, **self.metadata)
        return self

    def __bool__(self) -> bool:
        return self.success

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error_message,
            "error_code": self.error_code,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }

@dataclass
class PaginatedResult(Generic[T]):
    """Paginated result for list operations."""
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
    total_pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> PaginatedResult[T]:
        total_pages = max(1, (total + page_size - 1) // page_size)
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_prev=page > 1,
            total_pages=total_pages,
        )

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
            "total_pages": self.total_pages,
        }
