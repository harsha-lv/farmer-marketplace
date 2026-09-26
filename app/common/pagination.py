"""Canonical Keyset (Cursor-Based) Pagination and Filtering Standard.

Guarantees:
  - Keyset pagination (cursor-based: O(1) seek time, never suffers from OFFSET degradation on deep pages)
  - Base64 opaque cursor containing (sort_value, tiebreaker_id)
  - Strict sort allowlist to prevent arbitrary column scanning or injection
  - Keyset filtering:
      DESC: (sort_col < cursor_val) OR (sort_col == cursor_val AND id_col < cursor_id)
      ASC:  (sort_col > cursor_val) OR (sort_col == cursor_val AND id_col > cursor_id)
  - Conditional X-Total-Count header: omitted by default on massive tables, computed only when explicitly requested (include_total=True) or cheap
"""

import base64
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Generic, TypeVar

from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError

T = TypeVar("T")


def _json_serial(obj: Any) -> Any:
    """JSON serializer for cursor components (datetime, date, Decimal)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable in cursor")


def encode_cursor(sort_value: Any, id_value: Any) -> str:
    """Encode sort value and tiebreaker ID into an opaque Base64 URL-safe cursor string."""
    payload = json.dumps([sort_value, id_value], default=_json_serial)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor_str: str) -> tuple[Any, Any]:
    """Decode an opaque Base64 URL-safe cursor string into (sort_value, id_value).

    Raises AppError(422) if the cursor is malformed.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode("ascii")).decode("utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or len(parsed) != 2:
            raise ValueError("Cursor must be a 2-element tuple [sort_value, id_value]")
        return parsed[0], parsed[1]
    except Exception as exc:
        raise AppError(
            status_code=422,
            title="Invalid pagination cursor",
            detail=f"The supplied pagination cursor is malformed or invalid: {exc}",
        ) from exc


class KeysetPaginationParams(BaseModel):
    """Standard query parameters for keyset pagination endpoints."""

    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of items to return")
    cursor: str | None = Field(default=None, description="Opaque keyset cursor pointing to the next page")
    sort_by: str | None = Field(default=None, description="Column name to sort by (must be in sort allowlist)")
    order: str = Field(default="desc", pattern="^(asc|desc|ASC|DESC)$", description="Sort direction")
    include_total: bool = Field(
        default=False,
        description="Whether to perform a COUNT(*) query and return X-Total-Count header (expensive on large tables)",
    )


class PageMeta(BaseModel):
    """Metadata envelope for paginated collections."""

    limit: int
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None


class KeysetPage(BaseModel, Generic[T]):
    """Standard keyset page response container."""

    data: list[T]
    meta: PageMeta

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _coerce_sort_val(sort_col: Any, val: Any) -> Any:
    """Coerce decoded JSON cursor value back to Python type expected by the column."""
    if val is None:
        return None
    try:
        col_type = getattr(sort_col, "type", None)
        py_type = getattr(col_type, "python_type", None) if col_type is not None else None
        if py_type and issubclass(py_type, datetime) and isinstance(val, str):
            return datetime.fromisoformat(val)
        if py_type and issubclass(py_type, date) and isinstance(val, str):
            return date.fromisoformat(val)
        if py_type and issubclass(py_type, Decimal) and isinstance(val, (str, float, int)):
            return Decimal(str(val))
    except (ValueError, TypeError, InvalidOperation):
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                pass
    return val


class KeysetPaginator:
    """Executes keyset pagination over a SQLAlchemy select statement with sort allowlist."""

    def __init__(
        self,
        *,
        model: Any,
        id_column: ColumnElement,
        sort_allowlist: dict[str, ColumnElement],
        default_sort_field: str,
        default_order: str = "desc",
        max_limit: int = 200,
    ) -> None:
        self.model = model
        self.id_column = id_column
        self.sort_allowlist = sort_allowlist
        self.default_sort_field = default_sort_field
        self.default_order = default_order.lower()
        self.max_limit = max_limit

    def validate_sort_field(self, sort_field: str | None) -> tuple[str, ColumnElement]:
        """Validate requested sort column against the explicit sort allowlist."""
        if not sort_field:
            return self.default_sort_field, self.sort_allowlist[self.default_sort_field]
        clean_field = sort_field.strip().lower()
        if clean_field not in self.sort_allowlist:
            allowed = sorted(list(self.sort_allowlist.keys()))
            raise AppError(
                status_code=422,
                title="Invalid sort field",
                detail=f"Field '{sort_field}' is not allowed for sorting. Allowed fields: {allowed}",
            )
        return clean_field, self.sort_allowlist[clean_field]

    async def paginate(
        self,
        session: AsyncSession,
        statement: Select,
        *,
        cursor: str | None = None,
        limit: int = 50,
        sort_by: str | None = None,
        order: str = "desc",
        include_total: bool = False,
        response: Response | None = None,
    ) -> tuple[list[Any], str | None, bool, int | None]:
        """Apply keyset cursor and sort clauses, fetch limit + 1 items, and return (items, next_cursor, has_more, total_count)."""
        limit = min(max(1, limit), self.max_limit)
        order_dir = order.lower()
        sort_name, sort_col = self.validate_sort_field(sort_by)

        # 1. Total count only if explicitly requested (or cheap)
        total_count: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(statement.order_by(None).subquery())
            total_count = int(await session.scalar(count_stmt) or 0)
            if response is not None:
                response.headers["X-Total-Count"] = str(total_count)

        # 2. Keyset cursor filtering
        paginated_stmt = statement
        if cursor:
            c_sort_val, c_id_val = decode_cursor(cursor)
            c_sort_val = _coerce_sort_val(sort_col, c_sort_val)

            if order_dir == "desc":
                paginated_stmt = paginated_stmt.where(
                    or_(
                        sort_col < c_sort_val,
                        and_(sort_col == c_sort_val, self.id_column < c_id_val),
                    )
                )
            else:
                paginated_stmt = paginated_stmt.where(
                    or_(
                        sort_col > c_sort_val,
                        and_(sort_col == c_sort_val, self.id_column > c_id_val),
                    )
                )

        # 3. Order By
        if order_dir == "desc":
            paginated_stmt = paginated_stmt.order_by(sort_col.desc(), self.id_column.desc())
        else:
            paginated_stmt = paginated_stmt.order_by(sort_col.asc(), self.id_column.asc())

        # 4. Limit + 1 to detect next page
        paginated_stmt = paginated_stmt.limit(limit + 1)
        result = await session.scalars(paginated_stmt)
        rows = list(result.all())

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_more and items:
            last_item = items[-1]
            last_sort_val = getattr(last_item, sort_name)
            last_id_val = getattr(last_item, self.id_column.name)
            next_cursor = encode_cursor(last_sort_val, last_id_val)

        return items, next_cursor, has_more, total_count
