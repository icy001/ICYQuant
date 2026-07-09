from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None


class PagedResponse(BaseModel, Generic[T]):
    success: bool
    data: list[T]
    total: int
    page: int
    page_size: int
