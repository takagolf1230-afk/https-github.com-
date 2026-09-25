"""勝ちきり条件の集計と出走馬照合 → win_score。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .course_key import CourseKey, course_key_from_race, distance_band, track_type


def _finish(row: dict) -> int | None:
    for k in ("KakuteiJyuni", "kakutei_jyuni", "finish", "chakujun"):
        if k in row and row[k] not in (None, "", "00"):
            try:
                return int(row[k])
            except (TypeError, ValueError):
                return None
    return None


def _umaban(row: dict) -> int | None:
    for k in ("Umaban", "umaban", "horse_number"):
        if k in row and row[k] not in (None, ""):
            try:
                return int(row[k])
            except (TypeError, ValueError):
                return None
    return None


def _gate_band(umaban: int | None, field_size: int = 16) -> str:
    if umaban is None:
        return "unk"
    if umaban <= max(3, field_size // 5):
        return "inner"
    if umaban >= field_size - max(2, field_size // 5):
        return "outer"
    return "middle"


@dataclass
class HorseWinProfile:
    ketto: str
    starts: int = 0
    wins: int = 0
    places: int = 0  # top3
    by_course: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"starts": 0, "wins": 0, "places": 0}))
    by_coarse: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"starts": 0, "wins": 0, "places": 0}))
    by_gate: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"starts": 0, "wins": 0, "places": 0}))

    @property
    def win_rate(self) -> float:
        return self.wins / self.starts if self.starts else 0.0

    @property
    def place_rate(self) -> float:
        return self.places / self.starts if self.starts else 0.0

    @property
    def win_over_place(self) -> float:
        """勝ちきり指数。複勝ばかりだと低い。"""
        if self.place_rate <= 0:
            return 0.0
        return self.win_rate / self.place_rate


def build_profiles(past_by_horse: dict[str, list[dict]], race_meta_by_id: dict[str, dict] | None = None) -> dict[str, HorseWinProfile]:
    """過去走リストから馬プロフィールを構築。race_meta が無い場合は past 行自身から条件を読む。"""
    profiles: dict[str, HorseWinProfile] = {}
    for ketto, runs in past_by_horse.items():
        prof = HorseWinProfile(ketto=ketto)
        for run in runs:
            finish = _finish(run)
            if finish is None:
                continue
            meta = run
            if race_meta_by_id and run.get("race_id") in race_meta_by_id:
                meta = {**race_meta_by_id[run["race_id"]], **run}
            try:
                ck = course_key_from_race(meta)
            except Exception:
                continue
            prof.starts += 1
            if finish == 1:
                prof.wins += 1
            if finish <= 3:
                prof.places += 1
            for keystore, key in (
                (prof.by_course, ck.as_key()),
                (prof.by_coarse, ck.coarse_key()),
            ):
                keystore[key]["starts"] += 1
                if finish == 1:
                    keystore[key]["wins"] += 1
                if finish <= 3:
                    keystore[key]["places"] += 1
            gb = _gate_band(_umaban(run))
            prof.by_gate[gb]["starts"] += 1
            if finish == 1:
                prof.by_gate[gb]["wins"] += 1
            if finish <= 3:
                prof.by_gate[gb]["places"] += 1
        profiles[ketto] = prof
    return profiles


def _rate(d: dict[str, int], kind: str) -> float:
    s = d.get("starts", 0)
    if s <= 0:
        return 0.0
    return d.get(kind, 0) / s


def match_win_fit(profile: HorseWinProfile, course: CourseKey, umaban: int | None) -> float:
    """今走条件との照合スコア（生点）。"""
    fine = profile.by_course.get(course.as_key(), {})
    coarse = profile.by_coarse.get(course.coarse_key(), {})
    gate = profile.by_gate.get(_gate_band(umaban), {})

    score = 0.0
    # 同条件実績
    if fine.get("starts", 0) >= 1:
        score += 40 * _rate(fine, "wins") + 15 * _rate(fine, "places")
        score += min(fine.get("starts", 0), 3) * 2
    elif coarse.get("starts", 0) >= 1:
        score += 25 * _rate(coarse, "wins") + 10 * _rate(coarse, "places")
    else:
        score += 5 * profile.win_rate  # サンプル不足は控えめ

    score += 10 * profile.win_over_place
    score += 8 * _rate(gate, "wins")
    # 複勝はするが勝てない馬へのペナルティ
    if profile.place_rate >= 0.35 and profile.win_rate < 0.08 and profile.starts >= 5:
        score -= 8
    return score


def score_entries(
    entries: list[dict],
    profiles: dict[str, HorseWinProfile],
    course: CourseKey,
    horse_id_key: str = "KettoNum",
) -> list[dict[str, Any]]:
    """出走各馬に win_fit / win_score（レース内相対 0-100）を付与。"""
    raw: list[tuple[dict, float]] = []
    for e in entries:
        ketto = str(e.get(horse_id_key) or e.get("ketto_num") or e.get("horse_id") or "")
        prof = profiles.get(ketto) or HorseWinProfile(ketto=ketto)
        fit = match_win_fit(prof, course, _umaban(e))
        raw.append((e, fit))
    fits = [f for _, f in raw]
    lo, hi = (min(fits), max(fits)) if fits else (0.0, 0.0)
    span = hi - lo if hi > lo else 1.0
    out: list[dict[str, Any]] = []
    for e, fit in raw:
        row = dict(e)
        row["win_fit"] = round(fit, 3)
        row["win_score"] = round(100.0 * (fit - lo) / span, 2)
        ketto = str(e.get(horse_id_key) or e.get("ketto_num") or "")
        prof = profiles.get(ketto)
        row["place_score"] = round(100.0 * (prof.place_rate if prof else 0.0), 2)
        row["dark_score"] = 0.0
        if prof and prof.win_rate > 0 and row.get("win_score", 0) >= 40:
            # 人気が後で入る場合に上書き。ここでは勝ち実績ありを軽く加点
            row["dark_score"] = round(min(30.0, 100.0 * prof.win_rate), 2)
        out.append(row)
    out.sort(key=lambda r: (-r["win_score"], r.get("Umaban") or 0))
    return out
