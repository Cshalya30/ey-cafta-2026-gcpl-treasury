"""Shared response shapes.

Money is never a bare float in JSON. Every amount carries its currency and a
USD sibling, because cross-entity comparison is the whole point and a bare
number on a screen with eleven currencies is a defect waiting to be found.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    native: float = Field(description="Amount in the holder's own currency.")
    currency: str = Field(description="ISO 4217 code of the native amount.")
    usd: float = Field(description="The same amount converted at the as-of rate.")


def money(native: float, currency: str, fx_to_usd: float) -> Money:
    return Money(
        native=round(native, 2), currency=currency, usd=round(native * fx_to_usd, 2)
    )


class Coverage(BaseModel):
    """What share of the estate an aggregate actually covers.

    PRD 8.11: an aggregate without a coverage figure is a lie by omission.
    """

    accounts_total: int
    accounts_current: int
    pct: float
    statement: str


class Problem(BaseModel):
    """RFC 9457 problem details."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    cursor: str | None = None
    next_cursor: str | None = None


class PersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    holder_name: str
    office: str
    scope_kind: str
    scope_ref: str | None
    can_initiate: bool
    can_approve: bool
    can_settle: bool
    can_see_amounts: bool


class CitationOut(BaseModel):
    authority: str
    reference: str
    effect: str


class RouteOut(BaseModel):
    code: str
    name: str
    scope: str
    mechanism: str
    binding_constraint: str
    permits_movement: bool
    citations: list[CitationOut]
