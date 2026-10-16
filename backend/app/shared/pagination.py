"""Reusable pagination: query params + response envelope.

Envelope: {"items": [...], "total": int, "page": int, "page_size": int}
"""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(session: Session, query: Select, params: PageParams) -> tuple[list, int]:
    """Run count + slice against a SQLAlchemy Select; return (items, total)."""
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(query.limit(params.limit).offset(params.offset)).scalars().all()
    return list(rows), int(total)
