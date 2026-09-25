"""1レース分の予想パイプライン。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .course_key import course_key_from_race
from .gates import GateResult, apply_odds_floor
from .marks import assign_marks
from .race_pattern import RacePattern, classify_race
from .tickets import TicketPlan, build_tickets
from .win_match import HorseWinProfile, build_profiles, score_entries


@dataclass
class RacePrediction:
    race_id: str
    course_key: str
    pattern: RacePattern
    marked: list[dict]
    tickets: list[TicketPlan]
    gate: GateResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "race_id": self.race_id,
            "course_key": self.course_key,
            "pattern": asdict(self.pattern),
            "marked": [
                {
                    "Umaban": r.get("Umaban"),
                    "Bamei": r.get("Bamei"),
                    "mark": r.get("mark"),
                    "win_score": r.get("win_score"),
                    "place_score": r.get("place_score"),
                    "dark_score": r.get("dark_score"),
                }
                for r in self.marked
            ],
            "tickets": [
                {
                    "template_id": t.template_id,
                    "bet_type": t.bet_type,
                    "n_legs": len(t.legs),
                    "legs": t.legs[:30],
                    "reason": t.reason,
                }
                for t in self.tickets
            ],
            "gate": {
                "action": self.gate.action,
                "template_id": self.gate.template_id,
                "reason": self.gate.reason,
                "kept": len(self.gate.kept),
                "dropped": len(self.gate.dropped),
            },
        }


def predict_race(
    race: dict,
    entries: list[dict],
    past_by_horse: dict[str, list[dict]],
    race_id: str = "",
    odds_lookup: dict | None = None,
    course_hint: str = "",
) -> RacePrediction:
    course = course_key_from_race(race)
    profiles = build_profiles(past_by_horse)
    scored = score_entries(entries, profiles, course)
    pattern = classify_race(scored)
    marked = assign_marks(scored)
    plans = build_tickets(marked, pattern, course_hint=course_hint)
    gate = apply_odds_floor(plans, odds_lookup=odds_lookup)
    final_tickets = gate.kept if gate.action == "buy" else plans
    return RacePrediction(
        race_id=race_id or str(race.get("race_id") or ""),
        course_key=course.as_key(),
        pattern=pattern,
        marked=marked,
        tickets=final_tickets,
        gate=gate,
    )
