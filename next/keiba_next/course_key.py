"""レース・競馬場条件キー（勝ちきり照合用）。"""

from __future__ import annotations

from dataclasses import dataclass


def distance_band(distance_m: int) -> str:
    if distance_m <= 1300:
        return "sprint"
    if distance_m <= 1600:
        return "mile"
    if distance_m <= 2000:
        return "intermediate"
    if distance_m <= 2400:
        return "long"
    return "stayer"


def track_type(code: str | int | None) -> str:
    c = str(code or "").strip()
    if c in {"1", "芝", "turf", "T"}:
        return "turf"
    if c in {"2", "ダ", "ダート", "dirt", "D"}:
        return "dirt"
    return c or "unknown"


@dataclass(frozen=True)
class CourseKey:
    jyo: str
    track: str
    distance_band: str
    distance_m: int
    baba: str = "良"

    def as_key(self) -> str:
        return f"{self.jyo}|{self.track}|{self.distance_band}|{self.distance_m}|{self.baba}"

    def coarse_key(self) -> str:
        """サンプル不足時の粗いキー。"""
        return f"{self.jyo}|{self.track}|{self.distance_band}"


def course_key_from_race(race: dict) -> CourseKey:
    jyo = str(race.get("JyoCD") or race.get("jyo_cd") or race.get("venue") or "?")
    track = track_type(race.get("TrackCD") or race.get("track_cd") or race.get("track"))
    dist = int(race.get("Kyori") or race.get("distance") or race.get("kyori") or 0)
    baba = str(race.get("SibaBabaCD") or race.get("DirtBabaCD") or race.get("baba") or "良")
    # normalize baba codes if numeric
    baba_map = {"1": "良", "2": "稍", "3": "重", "4": "不"}
    baba = baba_map.get(baba, baba)
    return CourseKey(
        jyo=jyo,
        track=track,
        distance_band=distance_band(dist),
        distance_m=dist,
        baba=baba,
    )
