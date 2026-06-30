from __future__ import annotations

import math
from typing import Any, Generic, List, Optional, TypeVar

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, model_validator

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: str = "OK"
    data: Optional[DataT] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[DataT]):
    items: List[DataT]
    total: int
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    total_pages: int = 0

    @model_validator(mode="after")
    def compute_total_pages(self) -> "PaginatedResponse[DataT]":
        if self.page_size > 0:
            self.total_pages = math.ceil(self.total / self.page_size)
        return self
