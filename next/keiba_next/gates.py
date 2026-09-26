"""オッズ床・EVゲート。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tickets import TicketPlan

# 仮の床（100円あたり倍率）。バックテストで調整する。
ODDS_FLOOR = {
    "wide": 2.5,
    "umaren": 4.0,
    "umatan": 5.0,
    "sanrenpuku": 8.0,
    "sanrentan": 20.0,
    "win": 2.0,
}


@dataclass
class GateResult:
    template_id: str
    action: str  # buy / skip / T7
    kept: list[TicketPlan]
    dropped: list[tuple[TicketPlan, str]]
    reason: str


def _min_leg_odds(plan: TicketPlan, odds_lookup: dict[Any, float]) -> float | None:
    if not plan.legs:
        return None
    vals = []
    for leg in plan.legs:
        key = leg if plan.bet_type != "wide" else (min(leg[0], leg[1]), max(leg[0], leg[1]))
        # try exact then frozenset-ish
        o = odds_lookup.get(key)
        if o is None and len(leg) == 2:
            o = odds_lookup.get((leg[1], leg[0]))
        if o is not None:
            vals.append(float(o))
    if not vals:
        return None
    return min(vals)


def apply_odds_floor(
    plans: list[TicketPlan],
    odds_lookup: dict[Any, float] | None = None,
    floors: dict[str, float] | None = None,
) -> GateResult:
    floors = floors or ODDS_FLOOR
    odds_lookup = odds_lookup or {}
    if not plans:
        return GateResult("T7", "T7", [], [], "候補なしケン")

    if all(p.bet_type == "skip" for p in plans):
        p0 = plans[0]
        return GateResult(p0.template_id, "skip", plans, [], p0.reason)

    kept: list[TicketPlan] = []
    dropped: list[tuple[TicketPlan, str]] = []
    for p in plans:
        if p.bet_type == "skip":
            continue
        floor = floors.get(p.bet_type, 1.0)
        # filter each leg if odds known; if no odds, keep (backtest without odds)
        if not odds_lookup:
            kept.append(p)
            continue
        filtered_legs = []
        for leg in p.legs:
            o = odds_lookup.get(leg)
            if o is None and len(leg) >= 2:
                o = odds_lookup.get((leg[1], leg[0])) if len(leg) == 2 else None
            if o is None or float(o) >= floor:
                filtered_legs.append(leg)
        if filtered_legs:
            kept.append(
                TicketPlan(p.template_id, p.bet_type, filtered_legs, p.reason + " [floor]")
            )
        else:
            dropped.append((p, f"{p.bet_type} all below floor {floor}"))

    if not kept:
        return GateResult(
            plans[0].template_id,
            "T7",
            [],
            dropped,
            "オッズ過薄のためケン",
        )
    return GateResult(kept[0].template_id, "buy", kept, dropped, "床通過")


def filter_by_ev(
    plan: TicketPlan,
    prob_lookup: dict[Any, float],
    odds_lookup: dict[Any, float],
    ev_min: float = 0.8,
) -> TicketPlan:
    """EV = p * odds。簡易フィルタ。"""
    legs = []
    for leg in plan.legs:
        p = prob_lookup.get(leg, 0.0)
        o = odds_lookup.get(leg) or odds_lookup.get((leg[1], leg[0]) if len(leg) == 2 else leg)
        if o is None:
            legs.append(leg)
            continue
        if p * float(o) >= ev_min:
            legs.append(leg)
    return TicketPlan(plan.template_id, plan.bet_type, legs, plan.reason + " [ev]")
