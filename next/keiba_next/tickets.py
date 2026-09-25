"""券種テンプレ T1〜T7。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Any

from .marks import horses_by_mark
from .race_pattern import RacePattern


@dataclass
class TicketPlan:
    template_id: str
    bet_type: str
    legs: list[tuple]
    reason: str


def _nums(horses: list[dict]) -> list[int]:
    out = []
    for h in horses:
        n = h.get("Umaban") or h.get("umaban") or h.get("horse_number")
        if n is not None:
            out.append(int(n))
    return out


def select_template(pattern: RacePattern, course_hint: str = "") -> str:
    if pattern.name == "Chaos" or pattern.axis_confidence == "Low":
        return "T6"
    if pattern.name == "Solid":
        return "T1"
    if pattern.name == "AxisEdge":
        return "T3"
    # Mid
    if "small" in course_hint or "小回" in course_hint:
        return "T5"
    return "T4"


def build_tickets(
    marked: list[dict],
    pattern: RacePattern,
    course_hint: str = "",
    include_star_in_t3: bool = True,
) -> list[TicketPlan]:
    tid = select_template(pattern, course_hint)
    if tid == "T6":
        return [TicketPlan("T6", "skip", [], "混戦のためケン")]

    by = horses_by_mark(marked)
    axis = _nums(by.get("◎", []))
    opp = _nums(by.get("○", []) + by.get("▲", []) + by.get("△", []))
    star = _nums(by.get("☆", [])) if include_star_in_t3 else []

    if not axis:
        return [TicketPlan("T6", "skip", [], "軸なしケン")]

    a = axis[0]
    plans: list[TicketPlan] = []

    if tid == "T1":
        partners = opp[:3]
        legs = [(min(a, b), max(a, b)) for b in partners if b != a]
        plans.append(TicketPlan("T1", "wide", legs, "堅実: ◎→○▲△ ワイド"))
        plans.append(
            TicketPlan("T1", "umaren", legs[:2], "堅実: 馬連少点")
        )
    elif tid == "T3":
        partners = opp[:4]
        legs = [(min(a, b), max(a, b)) for b in partners if b != a]
        plans.append(TicketPlan("T3", "wide", legs, "軸堅下位荒れ: ワイド本線"))
        # 条件付き三連単フォーメーション
        second = _nums(by.get("○", []) + by.get("▲", []))[:2]
        third = list(dict.fromkeys(opp[:3] + star))[:4]
        trif = []
        for b in second:
            for c in third:
                if len({a, b, c}) == 3:
                    trif.append((a, b, c))
        plans.append(
            TicketPlan("T3", "sanrentan", trif[:12], "軸堅: 三連単F（穴根拠時）")
        )
    elif tid in {"T4", "T5"}:
        partners = opp[: 5 if tid == "T5" else 4]
        legs = [(min(a, b), max(a, b)) for b in partners if b != a]
        plans.append(TicketPlan(tid, "wide", legs, "中荒れ: ワイド"))
        # 三連複: 軸+相手から3頭組合せ
        pool = [a] + partners
        trio = [tuple(sorted(c)) for c in combinations(pool, 3)]
        plans.append(TicketPlan(tid, "sanrenpuku", trio[:20], "中荒れ: 三連複"))
    else:  # T2-like formation if ever selected
        second = opp[:2]
        third = opp[:4]
        trif = list(permutations([a] + second[:1] + third[:2], 3))  # noqa: simplistic
        plans.append(TicketPlan("T2", "sanrentan", [], "reserved"))

    return plans
