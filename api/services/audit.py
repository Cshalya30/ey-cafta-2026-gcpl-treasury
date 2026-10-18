"""SHA-256 audit hash chain (PRD section 9.4).

The only write path is append(). There is no update and no delete, here or
anywhere else in the codebase, which is what makes verify() meaningful.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent, Persona

GENESIS_HASH = "0" * 64


def payload_for(
    *,
    prev_hash: str,
    ts: str,
    actor_id: str,
    action: str,
    obj_kind: str,
    obj_id: str,
    detail: str,
    justification: str | None,
) -> str:
    """The exact string that is hashed. Field order is part of the contract."""
    return (
        f"{prev_hash}|{ts}|{actor_id}|{action}|{obj_kind}|{obj_id}|"
        f"{detail}|{justification or ''}"
    )


def digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append(
    session: Session,
    *,
    actor: Persona,
    action: str,
    obj_kind: str,
    obj_id: str,
    detail: str,
    justification: str | None = None,
    ts: str | None = None,
) -> AuditEvent:
    """Append one event, chained to the current tail. Flushes so seq is assigned."""
    prev = session.execute(
        select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = prev.hash if prev else GENESIS_HASH
    stamp = ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    event = AuditEvent(
        ts=stamp,
        actor_persona=actor.id,
        actor_name=actor.holder_name,
        action=action,
        object_kind=obj_kind,
        object_id=obj_id,
        detail=detail,
        justification=justification,
        prev_hash=prev_hash,
        hash=digest(
            payload_for(
                prev_hash=prev_hash,
                ts=stamp,
                actor_id=actor.id,
                action=action,
                obj_kind=obj_kind,
                obj_id=obj_id,
                detail=detail,
                justification=justification,
            )
        ),
    )
    session.add(event)
    session.flush()
    return event


@dataclass(frozen=True)
class ChainResult:
    intact: bool
    broken_at: int | None
    checked: int
    reason: str | None = None


def verify(session: Session) -> ChainResult:
    """Recompute every hash from seq=1 and report the first mismatch."""
    events = session.execute(select(AuditEvent).order_by(AuditEvent.seq.asc())).scalars().all()
    expected_prev = GENESIS_HASH

    for index, event in enumerate(events, start=1):
        if event.prev_hash != expected_prev:
            return ChainResult(
                intact=False,
                broken_at=event.seq,
                checked=index,
                reason=(
                    f"Event {event.seq} links to {event.prev_hash[:12]}… but the "
                    f"preceding event hashes to {expected_prev[:12]}…"
                ),
            )
        recomputed = digest(
            payload_for(
                prev_hash=event.prev_hash,
                ts=event.ts,
                actor_id=event.actor_persona,
                action=event.action,
                obj_kind=event.object_kind,
                obj_id=event.object_id,
                detail=event.detail,
                justification=event.justification,
            )
        )
        if recomputed != event.hash:
            return ChainResult(
                intact=False,
                broken_at=event.seq,
                checked=index,
                reason=(
                    f"Event {event.seq} content hashes to {recomputed[:12]}… but "
                    f"stores {event.hash[:12]}…. The row was altered after it was written."
                ),
            )
        expected_prev = event.hash

    return ChainResult(intact=True, broken_at=None, checked=len(events))
