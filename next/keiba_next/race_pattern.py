"""レース構造 Soft/AxisEdge/Mid/Chaos。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Pattern = Literal["Solid", "AxisEdge", "Mid", "Chaos"]


@dataclass(frozen=True)
class RacePattern:
    name: Pattern
    top_gap: float
    top_sum: float
    axis_confidence: str  # High/Mid/Low
    field_chaos: str  # High/Low


def classify_race(scored: list[dict], place_spread: float | None = None) -> RacePattern:
    """win_score 上位からパターン分類。"""
    if not scored:
        return RacePattern("Chaos", 0.0, 0.0, "Low", "High")
    scores = [float(r.get("win_score") or 0.0) for r in scored]
    s1 = scores[0]
    s2 = scores[1] if len(scores) > 1 else 0.0
    s3 = scores[2] if len(scores) > 2 else 0.0
    top_gap = s1 - s2
    top_sum = s1 + s2 + s3

    # place 上位と win 上位の食い違いで下位荒れを近似
    chaos = "Low"
    if place_spread is None and len(scored) >= 3:
        by_place = sorted(scored, key=lambda r: (-float(r.get("place_score") or 0), 0))
        win_top3 = {id(r) for r in scored[:3]}
        place_top3 = {id(r) for r in by_place[:3]}
        if len(win_top3 & place_top3) <= 1:
            chaos = "High"
    elif place_spread is not None and place_spread > 0.5:
        chaos = "High"

    if top_gap >= 25 and s1 >= 70:
        axis = "High"
        name: Pattern = "AxisEdge" if chaos == "High" else "Solid"
    elif top_gap >= 12 and s1 >= 55:
        axis = "Mid"
        name = "Mid"
    else:
        axis = "Low"
        name = "Chaos"

    return RacePattern(name, round(top_gap, 2), round(top_sum, 2), axis, chaos)
