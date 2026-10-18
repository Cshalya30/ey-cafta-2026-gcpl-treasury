"""The four-test account rationalisation scorer (PRD section 8.4).

Every account scores 0 to 4. Disposition follows from the score, not from an
opinion: 4 = keep, 2 or 3 = migrate, 0 or 1 = close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Bank, BankCountryCoverage, Entity

ACTIVITY_WINDOW_DAYS = 90

# Phrases that mark a restriction as statutory rather than administrative.
STATUTORY_MARKERS = (
    "statutory",
    "mandated",
    "required by",
    "regulation",
    "escrow",
    "exchange control",
    "ring-fenc",
)


@dataclass(frozen=True)
class AccountScore:
    account_id: str
    score_panel: int
    score_unique: int
    score_active: int
    score_legal: int
    disposition: str
    reasons: list[str]

    @property
    def total(self) -> int:
        return self.score_panel + self.score_unique + self.score_active + self.score_legal


def disposition_for(total: int) -> str:
    if total >= 4:
        return "keep"
    if total >= 2:
        return "migrate"
    return "close"


def score_accounts(
    session: Session,
    account_ids: list[str] | None = None,
    as_of: date | None = None,
) -> list[AccountScore]:
    """Score a filter set. Pure computation; persistence is the caller's choice."""
    as_of = as_of or date.today()
    cutoff = as_of - timedelta(days=ACTIVITY_WINDOW_DAYS)

    query = select(Account)
    if account_ids is not None:
        query = query.where(Account.id.in_(account_ids))
    accounts = list(session.execute(query).scalars())

    entity_country = dict(session.execute(select(Entity.id, Entity.country_iso2)).all())
    panel_banks = set(
        session.execute(select(Bank.id).where(Bank.panel_status == "panel")).scalars().all()
    )
    coverage = {
        (bank_id, iso2)
        for bank_id, iso2, can_serve in session.execute(
            select(
                BankCountryCoverage.bank_id,
                BankCountryCoverage.country_iso2,
                BankCountryCoverage.can_serve,
            )
        ).all()
        if can_serve
    }

    # T2 needs every account in the entity, not only the filtered subset, or a
    # filter would change an account's score. Scores must be filter-independent.
    purpose_counts: dict[tuple[str, str, str], int] = {}
    for entity_id, purpose, currency in session.execute(
        select(Account.entity_id, Account.purpose, Account.currency)
    ).all():
        key = (entity_id, purpose, currency)
        purpose_counts[key] = purpose_counts.get(key, 0) + 1

    results: list[AccountScore] = []
    for account in accounts:
        reasons: list[str] = []
        country = entity_country.get(account.entity_id, "")

        panel = int(account.bank_id in panel_banks and (account.bank_id, country) in coverage)
        reasons.append(
            f"T1 panel coverage: {'yes' if panel else 'no'} — bank is "
            f"{'on' if account.bank_id in panel_banks else 'off'} panel and "
            f"{'does' if (account.bank_id, country) in coverage else 'does not'} "
            f"serve {country or 'this country'}."
        )

        unique = int(purpose_counts.get((account.entity_id, account.purpose, account.currency), 0) <= 1)
        duplicates = purpose_counts.get(
            (account.entity_id, account.purpose, account.currency), 0
        )
        reasons.append(
            f"T2 unique purpose: {'yes' if unique else 'no'} — {duplicates} account(s) "
            f"in {account.entity_id} share purpose '{account.purpose}' in {account.currency}."
        )

        active = int(account.last_movement is not None and account.last_movement >= cutoff)
        reasons.append(
            f"T3 activity: {'yes' if active else 'no'} — last movement "
            f"{account.last_movement.isoformat() if account.last_movement else 'never'} "
            f"against a {ACTIVITY_WINDOW_DAYS}-day window from {cutoff.isoformat()}."
        )

        note = (account.restriction_note or "").lower()
        legal = int(bool(note) and any(marker in note for marker in STATUTORY_MARKERS))
        reasons.append(
            f"T4 legal necessity: {'yes' if legal else 'no'} — "
            f"{'statutory requirement recorded' if legal else 'no statutory requirement recorded'}."
        )

        total = panel + unique + active + legal
        results.append(
            AccountScore(
                account_id=account.id,
                score_panel=panel,
                score_unique=unique,
                score_active=active,
                score_legal=legal,
                disposition=disposition_for(total),
                reasons=reasons,
            )
        )
    return results


def persist_scores(session: Session, scores: list[AccountScore]) -> int:
    """Write scores back onto the account rows. Returns the number updated."""
    by_id = {s.account_id: s for s in scores}
    updated = 0
    for account in session.execute(
        select(Account).where(Account.id.in_(list(by_id)))
    ).scalars():
        score = by_id[account.id]
        account.score_panel = score.score_panel
        account.score_unique = score.score_unique
        account.score_active = score.score_active
        account.score_legal = score.score_legal
        account.disposition = score.disposition
        updated += 1
    session.flush()
    return updated
