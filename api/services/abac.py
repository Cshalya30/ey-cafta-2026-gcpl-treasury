"""Attribute-based access control (PRD section 9.3).

Scope is resolved from persona attributes and applied in the repository layer,
never in the router and never in the browser. An out-of-scope entity produces
403, not a filtered 200: a filtered 200 tells the caller the entity does not
exist, which is a different and false statement.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Entity, Persona


class ScopeError(PermissionError):
    """Raised when a persona reaches outside its own scope."""

    def __init__(self, persona: Persona, requested: str) -> None:
        self.persona = persona
        self.requested = requested
        super().__init__(f"{persona.id} may not read {requested}")

    def describe_scope(self) -> str:
        """Plain English for the 403 body. Names the real scope, per PRD 8.11."""
        match self.persona.scope_kind:
            case "group":
                return "the whole group"
            case "region":
                return f"region {self.persona.scope_ref}"
            case "entity":
                return f"entity {self.persona.scope_ref}"
            case _:
                return "platform infrastructure only, with no financial data"


def all_entity_ids(session: Session) -> set[str]:
    return set(session.execute(select(Entity.id)).scalars().all())


def entities_in_region(region_id: str | None, session: Session) -> set[str]:
    if region_id is None:
        return set()
    return set(
        session.execute(
            select(Entity.id).where(Entity.region_id == region_id)
        ).scalars().all()
    )


def visible_entity_ids(persona: Persona, session: Session) -> set[str]:
    match persona.scope_kind:
        case "group":
            return all_entity_ids(session)
        case "region":
            return entities_in_region(persona.scope_ref, session)
        case "entity":
            return {persona.scope_ref} if persona.scope_ref else set()
        case "platform":
            # IT administers feeds and connectivity. It never sees amounts.
            return set()
        case _:
            return set()


def require_entity(persona: Persona, entity_id: str, session: Session) -> None:
    if entity_id not in visible_entity_ids(persona, session):
        raise ScopeError(persona, entity_id)


def can_see_amounts(persona: Persona) -> bool:
    return bool(persona.can_see_amounts) and persona.scope_kind != "platform"
