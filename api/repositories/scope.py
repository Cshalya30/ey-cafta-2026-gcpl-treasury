"""The scope dependency every endpoint must declare.

Scope resolution happens here, once, so no router can forget it. The test in
api/tests/test_scope_enforced.py enumerates the route table and fails if any
endpoint is missing this dependency, which is the enforcement mechanism the
PRD asks for in section 9.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Persona
from ..services import abac, metrics


@dataclass(frozen=True)
class Scope:
    """One request's view of the world."""

    persona: Persona
    entity_ids: frozenset[str]
    as_of: date
    session: Session

    def require(self, entity_id: str) -> None:
        """403 for anything outside scope. Never a filtered 200."""
        if entity_id not in self.entity_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "https://gcpl.local/problems/out-of-scope",
                    "title": "This entity is outside your scope.",
                    "status": 403,
                    "detail": (
                        f"{self.persona.display_name} ({self.persona.id}) is scoped to "
                        f"{abac.ScopeError(self.persona, entity_id).describe_scope()}. "
                        f"{entity_id} is not within it. This is an access decision, "
                        f"not a statement that the entity does not exist."
                    ),
                    "instance": f"/entities/{entity_id}",
                },
            )

    def filter(self, entity_ids: list[str]) -> list[str]:
        return [e for e in entity_ids if e in self.entity_ids]

    @property
    def sees_amounts(self) -> bool:
        return abac.can_see_amounts(self.persona)

    def require_amounts(self) -> None:
        if not self.sees_amounts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "https://gcpl.local/problems/no-financial-visibility",
                    "title": "This persona has no financial data visibility.",
                    "status": 403,
                    "detail": (
                        f"{self.persona.display_name} ({self.persona.id}) administers "
                        f"platform infrastructure. Feeds and connectivity are visible; "
                        f"amounts are not."
                    ),
                    "instance": None,
                },
            )

    def require_persona_in(self, allowed: set[str], action: str) -> None:
        """Gate an action on an explicit persona list, naming who may do it."""
        if self.persona.id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "https://gcpl.local/problems/persona-denied",
                    "title": f"This persona cannot {action}.",
                    "status": 403,
                    "detail": (
                        f"{self.persona.display_name} ({self.persona.id}) is not "
                        f"authorised to {action}. This action is held by "
                        f"{', '.join(sorted(allowed))}."
                    ),
                    "instance": None,
                },
            )

    def require_capability(self, capability: str) -> None:
        allowed = {
            "initiate": self.persona.can_initiate,
            "approve": self.persona.can_approve,
            "settle": self.persona.can_settle,
        }.get(capability, 0)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "https://gcpl.local/problems/capability-denied",
                    "title": f"This persona cannot {capability}.",
                    "status": 403,
                    "detail": (
                        f"{self.persona.display_name} ({self.persona.id}) holds no "
                        f"{capability} capability. Hiding the control in the browser is "
                        f"not the control; this rejection is."
                    ),
                    "instance": None,
                },
            )


def current_scope(
    x_persona: str = Header(
        default=...,
        alias="X-Persona",
        max_length=8,
        pattern="^P([1-9]|10)$",
        description="Acting persona, P1 to P10. Scope is resolved from it server-side.",
    ),
    session: Session = Depends(get_session),
) -> Scope:
    persona = session.execute(
        select(Persona).where(Persona.id == x_persona)
    ).scalar_one_or_none()

    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://gcpl.local/problems/unknown-persona",
                "title": "Unknown persona.",
                "status": 400,
                "detail": f"No persona {x_persona} exists. Send X-Persona as P1 to P10.",
                "instance": None,
            },
        )

    return Scope(
        persona=persona,
        entity_ids=frozenset(abac.visible_entity_ids(persona, session)),
        as_of=metrics.latest_as_of(session),
        session=session,
    )
