"""過去走だけから LightGBM 用の特徴量を作る。当該走の着順・オッズは入れない。"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from .course_key import distance_band
from .lgbm_model import FEATURE_NAMES, relevance


def _date_key(row: dict) -> str:
    if row.get("race_date"):
        return str(row["race_date"])
    y = int(row["Year"])
    md = int(row["MonthDay"])
    return f"{y:04d}{md:04d}"


def _race_key(row: dict) -> str:
    if row.get("race_id"):
        return str(row["race_id"])
    return (
        f"{_date_key(row)}|{row.get('JyoCD')}|{row.get('Kaiji')}|"
        f"{row.get('Nichiji')}|{row.get('RaceNum')}"
    )


def _finish(row: dict) -> int | None:
    v = row.get("KakuteiJyuni")
    if v in (None, "", "00"):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if 1 <= n <= 18:
        return n
    return None


def feature_vector(past: list[dict], today: dict) -> np.ndarray:
    """past は当該レースより前の走のみ。"""
    finishes = [f for f in (_finish(r) for r in past) if f is not None]
    n = len(finishes)
    wins = sum(1 for f in finishes if f == 1)
    places = sum(1 for f in finishes if f <= 3)
    win_rate = wins / n if n else 0.0
    place_rate = places / n if n else 0.0
    inv_avg = 0.0
    if finishes:
        inv_avg = 1.0 / (sum(finishes) / n)

    jyo = str(today.get("JyoCD") or "")
    dist = int(today.get("Kyori") or today.get("distance") or 0)
    band = distance_band(dist) if dist else ""

    def _subset_win_rate(pred) -> float:
        sub = [r for r in past if pred(r) and _finish(r) is not None]
        if not sub:
            return 0.0
        return sum(1 for r in sub if _finish(r) == 1) / len(sub)

    same_jyo = _subset_win_rate(lambda r: str(r.get("JyoCD") or "") == jyo)
    same_dist = _subset_win_rate(
        lambda r: distance_band(int(r.get("Kyori") or r.get("distance") or 0)) == band
        if band
        else False
    )
    wop = (win_rate / place_rate) if place_rate > 0 else 0.0
    vec = np.array(
        [n, win_rate, place_rate, inv_avg, same_jyo, same_dist, wop],
        dtype=float,
    )
    if len(vec) != len(FEATURE_NAMES):
        raise RuntimeError("feature length mismatch")
    return vec


def build_training_rows(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """確定着順がある走だけを学習行にする。特徴はそれより前の同馬の走。"""
    by_horse: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        ketto = str(r.get("KettoNum") or "")
        if ketto:
            by_horse[ketto].append(r)
    for runs in by_horse.values():
        runs.sort(key=_date_key)

    # group rows by race, only labeled
    races: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if _finish(r) is None:
            continue
        races[_race_key(r)].append(r)

    xs: list[np.ndarray] = []
    ys: list[int] = []
    groups: list[int] = []
    for key in sorted(races):
        members = races[key]
        if len(members) < 2:
            continue
        race_date = _date_key(members[0])
        block_x = []
        block_y = []
        for m in members:
            ketto = str(m["KettoNum"])
            past = [p for p in by_horse[ketto] if _date_key(p) < race_date and _finish(p)]
            block_x.append(feature_vector(past, m))
            block_y.append(relevance(_finish(m) or 99))
        xs.extend(block_x)
        ys.extend(block_y)
        groups.append(len(block_x))

    if not xs:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)), []
    return np.vstack(xs), np.asarray(ys, dtype=float), groups


def build_predict_matrix(entries: list[dict], past_by_horse: dict[str, list[dict]], race: dict) -> np.ndarray:
    today = {**race}
    rows = []
    for e in entries:
        ketto = str(e.get("KettoNum") or "")
        merged = {**race, **e}
        past = past_by_horse.get(ketto, [])
        rows.append(feature_vector(past, merged if merged.get("JyoCD") else today))
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES)))
    return np.vstack(rows)
