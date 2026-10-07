"""
Common Pydantic Schemas
Provides standard envelope and pagination metadata.
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Metadata for paginated list responses."""

    model_config = ConfigDict(from_attributes=True)

    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class APIResponse(BaseModel, Generic[T]):
    """Standard ORBIT API response envelope."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: Optional[T] = None
    meta: Optional[Any] = None
    error: Optional[str] = None


def api_response(
    data: Any = None,
    meta: Optional[Any] = None,
    error: Optional[str] = None,
    success: Optional[bool] = None,
) -> dict:
    """Helper function to build standard response dictionary."""
    is_success = success if success is not None else (error is None)
    meta_dict = None
    if meta is not None:
        if hasattr(meta, "model_dump"):
            meta_dict = meta.model_dump()
        elif isinstance(meta, dict):
            meta_dict = meta
        else:
            meta_dict = meta

    return {
        "success": is_success,
        "data": data,
        "meta": meta_dict,
        "error": error,
    }
