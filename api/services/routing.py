"""The India routing model and the Rule 10TD safe-harbour floor (PRD section 10).

Citations are data here so the UI can render the authority rather than the
assertion. The product must never render "RBI prohibits notional pooling";
it renders the three conditions that are individually blocked.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    authority: str
    reference: str
    effect: str


@dataclass(frozen=True)
class Route:
    code: str
    name: str
    scope: str
    mechanism: str
    binding_constraint: str
    permits_movement: bool
    citations: tuple[Citation, ...]


NOTIONAL_POOLING_STATEMENT = (
    "Notional pooling is not an available structure for Indian resident entities, "
    "because the enabling conditions are individually blocked."
)

NOTIONAL_POOLING_CITATIONS: tuple[Citation, ...] = (
    Citation(
        authority="Reserve Bank of India",
        reference="Master Direction DBR.Dir.No.84/13.03.00/2015-16, s.5",
        effect="No interest may be paid on current accounts, so offset economics cannot be credited.",
    ),
    Citation(
        authority="Parliament of India",
        reference="FEMA 1999, ss.3, 4 and 6(1)",
        effect="Resident-to-non-resident transfers are not permitted except as enabled.",
    ),
    Citation(
        authority="Reserve Bank of India",
        reference="Notification FEMA 3(R)/2018-RB, Schedule III",
        effect="Resident-to-non-resident lending is confined to five enumerated cases.",
    ),
)

GIFT_CITY_CAVEAT = (
    "An IFSC unit is a person resident outside India under FEMA 339/2015-RB, reg. 3. "
    "The Indian parent's leg into a GIFT City pool therefore remains a cross-border "
    "transaction requiring ODI or ECB cover. The IFSCA GRCTC Framework of 4 April 2025 "
    "expressly permits pooling of funds at Annex II item 7, but it creates no FEMA "
    "exemption for the resident entity. Both facts must be shown together."
)

ROUTES: dict[str, Route] = {
    "A": Route(
        code="A",
        name="India domestic",
        scope="Resident-to-resident, single currency",
        mechanism="Physical sweep between resident entities under documented intercompany agreements",
        binding_constraint=(
            "No notional offset. Indian banks may not pay interest on current accounts."
        ),
        permits_movement=True,
        citations=NOTIONAL_POOLING_CITATIONS[:1],
    ),
    "B": Route(
        code="B",
        name="Offshore regional",
        scope="Non-resident to non-resident",
        mechanism=(
            "Physical pools headed in Singapore or the Netherlands, with an optional "
            "GIFT City GRCTC header"
        ),
        binding_constraint="The header account must sit with an IBU or IBC.",
        permits_movement=True,
        citations=(
            Citation(
                authority="IFSCA",
                reference="GRCTC Framework, 4 April 2025, Annex II item 7",
                effect="Pooling of funds is an expressly permitted GRCTC activity.",
            ),
        ),
    ),
    "C": Route(
        code="C",
        name="India cross-border",
        scope="One Indian resident leg",
        mechanism="ODI or ECB only, under documented loan agreements",
        binding_constraint=(
            "ODI needs prior equity and control. The AD bank must hold the loan "
            "agreement before remitting."
        ),
        permits_movement=True,
        citations=NOTIONAL_POOLING_CITATIONS[1:],
    ),
    "D": Route(
        code="D",
        name="Restricted",
        scope="Exchange-controlled jurisdictions",
        mechanism="Cash stays local, is monitored, and is never swept",
        binding_constraint="Exchange control. Trapped cash is declared, not hidden.",
        permits_movement=False,
        citations=(),
    ),
}


# ─────────────── Rule 10TD safe-harbour floor (LR11, pooling check 6) ───────────────

# Rule 10TD of the Income-tax Rules 1962 applies to AY 2020-21 through AY 2026-27
# under sub-rule (3B). The Income-tax Act 2025 and Rules 2026 took effect on
# 1 April 2026 and the renumbering is unconfirmed; the applicability note travels
# with every citation the UI renders. See PRD Appendix D.
RULE_10TD_NOTE = (
    "Rule 10TD, Income-tax Rules 1962, applicable AY 2020-21 to AY 2026-27 under "
    "sub-rule (3B). Renumbering under the Rules 2026 is unconfirmed; verify against "
    "the gazette before presenting."
)

SAFE_HARBOUR_INR: dict[str, int] = {
    "AAA_to_A": 175,
    "BBB_band": 325,
    "BB_to_B": 475,
    "C_to_D": 625,
    "unrated": 425,
}

REFERENCE_FX: dict[str, tuple[str, int]] = {
    "USD": ("6M Term SOFR", 45),
    "EUR": ("6M EURIBOR", 0),
    "GBP": ("6M Term SONIA", 30),
    "JPY": ("6M TORF", 10),
    "AUD": ("6M BBSW", 0),
    "SGD": ("6M SORA", 45),
}

# Foreign-currency spreads tier by aggregate AE loan size, in basis points.
FX_SIZE_SPREADS_UPTO_250CR: tuple[int, ...] = (150, 300, 400)
FX_SIZE_SPREADS_ABOVE_250CR: tuple[int, ...] = (150, 300, 450, 600)

# INR 250 crore, expressed in INR.
SIZE_THRESHOLD_INR = 2_500_000_000  # INR 250 crore

# Benchmark levels as published on the reference dates. Stored as data so a judge
# can change one and watch every floor move.
BENCHMARK_LEVELS: dict[str, float] = {
    "SBI_1Y_MCLR": 0.0915,
    "6M Term SOFR": 0.0428,
    "6M EURIBOR": 0.0241,
    "6M Term SONIA": 0.0455,
    "6M TORF": 0.0071,
    "6M BBSW": 0.0412,
    "6M SORA": 0.0309,
}

RATING_BANDS = tuple(SAFE_HARBOUR_INR.keys())


@dataclass(frozen=True)
class SafeHarbour:
    floor: float
    basis: str
    citation: str

    def as_dict(self) -> dict:
        return {"floor": self.floor, "basis": self.basis, "citation": self.citation}


def _fx_size_spread(size_usd: float, usd_inr: float, rating_band: str) -> int:
    size_inr = size_usd * usd_inr
    tiers = (
        FX_SIZE_SPREADS_ABOVE_250CR
        if size_inr > SIZE_THRESHOLD_INR
        else FX_SIZE_SPREADS_UPTO_250CR
    )
    index = min(RATING_BANDS.index(rating_band), len(tiers) - 1)
    return tiers[index]


def safe_harbour_floor(
    currency: str,
    rating_band: str = "BBB_band",
    size_usd: float = 0.0,
    usd_inr: float = 83.0,
) -> SafeHarbour:
    """The minimum arm's-length intercompany rate for this currency and rating.

    INR loans price off the SBI one-year MCLR as on 1 April plus a rating spread.
    Foreign-currency loans price off the stated reference rate as on 30 September
    plus a spread that tiers by aggregate AE loan size.
    """
    band = rating_band if rating_band in SAFE_HARBOUR_INR else "unrated"

    if currency == "INR":
        spread_bps = SAFE_HARBOUR_INR[band]
        base = BENCHMARK_LEVELS["SBI_1Y_MCLR"]
        return SafeHarbour(
            floor=round(base + spread_bps / 10_000, 6),
            basis=f"SBI 1-yr MCLR {base:.4f} + {spread_bps}bps ({band})",
            citation=RULE_10TD_NOTE,
        )

    reference, base_spread_bps = REFERENCE_FX.get(currency, ("6M Term SOFR", 45))
    base = BENCHMARK_LEVELS.get(reference, BENCHMARK_LEVELS["6M Term SOFR"])
    size_spread = _fx_size_spread(size_usd, usd_inr, band)
    total_bps = base_spread_bps + size_spread
    return SafeHarbour(
        floor=round(base + total_bps / 10_000, 6),
        basis=f"{reference} {base:.4f} + {base_spread_bps}bps + {size_spread}bps ({band})",
        citation=RULE_10TD_NOTE,
    )


def route_for(country_iso2: str, routes_by_country: dict[str, str]) -> Route:
    return ROUTES[routes_by_country.get(country_iso2, "B")]
