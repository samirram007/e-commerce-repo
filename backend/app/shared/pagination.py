"""Reusable pagination + server-side list helpers: query params + envelope.

Envelope: {"items": [...], "total": int, "page": int, "page_size": int}

`ListParams` is the standard dependency for list endpoints that support
server-side search, sort and pagination. Sort fields are validated against a
per-endpoint allowlist — never interpolate client input into SQL (AGENT.md §8).
"""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError

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


def paginate(session: Session, query: Select, params: "PageParams | ListParams") -> tuple[list, int]:
    """Run count + slice against a SQLAlchemy Select; return (items, total)."""
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(query.limit(params.limit).offset(params.offset)).scalars().all()
    return list(rows), int(total)


ORDER_BY_VALUES = ("asc", "desc")


class ListParams(PageParams):
    """Standard server-side list query params.

    As a FastAPI dependency: `params: ListParams = Depends()`.
    - `search`: free-text term, matched (case-insensitive) against the
      endpoint's `search_fields` via `apply_list`.
    - `sort` / `order`: column allowlist validated in `apply_list`; unknown
      columns raise `INVALID_SORT_FIELD` instead of reaching SQL.
    """

    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        search: str | None = Query(None, max_length=200),
        sort: str | None = Query(None, max_length=64),
        order: str = Query("asc", pattern="^(asc|desc)$"),
    ) -> None:
        super().__init__(page=page, page_size=page_size)
        self.search = search.strip() if search else None
        self.sort = sort
        self.order = order


def apply_list(
    query: Select,
    model,
    params: ListParams,
    *,
    search_fields: tuple[str, ...] = (),
    sortable_fields: tuple[str, ...] = (),
    default_sort: tuple[str, bool] | None = None,
) -> Select:
    """Apply server-side search + validated sort to a company-scoped Select.

    Args:
        query: base Select (company filter already applied by the caller).
        model: ORM model owning the columns (getattr'd, never client strings
            interpolated into SQL).
        params: the resolved ListParams dependency.
        search_fields: model attribute names OR-ed together for `params.search`.
        sortable_fields: allowlist for `params.sort`; anything else is rejected.
        default_sort: (attribute_name, descending) applied when no valid sort
            is requested.
    """
    if params.search and search_fields:
        term = f"%{params.search}%"
        query = query.where(
            or_(*[getattr(model, name).ilike(term) for name in search_fields])
        )

    sort_desc = params.order == "desc"
    if params.sort:
        if params.sort not in sortable_fields:
            raise BusinessRuleError(
                "INVALID_SORT_FIELD",
                f"Cannot sort by '{params.sort}'. Allowed: {', '.join(sortable_fields)}",
            )
        query = query.order_by(getattr(model, params.sort).desc() if sort_desc else getattr(model, params.sort).asc())
    elif default_sort:
        name, descending = default_sort
        query = query.order_by(getattr(model, name).desc() if descending else getattr(model, name).asc())
    return query
