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


def _num(row: dict, *keys: str) -> float | None:
    for k in keys:
        if k not in row or row[k] in (None, "", "0", "00", "000"):
            continue
        try:
            return float(row[k])
        except (TypeError, ValueError):
            continue
    return None


def _agari(row: dict) -> float:
    raw = _num(row, "HaronTimeL3", "Agari", "agari", "TimeL3")
    if raw is None:
        return 0.0
    if raw > 100:
        raw = raw / 10.0
    return raw


def _days_between(newer: str, older: str) -> float:
    try:
        from datetime import datetime

        a = datetime.strptime(newer, "%Y%m%d")
        b = datetime.strptime(older, "%Y%m%d")
        return float((a - b).days)
    except ValueError:
        return 0.0


def feature_vector(past: list[dict], today: dict) -> np.ndarray:
    """過去走と今走の条件から複数ファクターを作る。今走の着順・オッズは入れない。"""
    finishes = [f for f in (_finish(r) for r in past) if f is not None]
    n = len(finishes)
    wins = sum(1 for f in finishes if f == 1)
    rentai = sum(1 for f in finishes if f <= 2)
    places = sum(1 for f in finishes if f <= 3)
    win_rate = wins / n if n else 0.0
    rentai_rate = rentai / n if n else 0.0
    place_rate = places / n if n else 0.0
    inv_avg = (1.0 / (sum(finishes) / n)) if finishes else 0.0

    jyo = str(today.get("JyoCD") or "")
    dist = int(today.get("Kyori") or today.get("distance") or 0)
    band = distance_band(dist) if dist else ""
    track = str(today.get("TrackCD") or today.get("track") or "")

    def _subset_rate(pred, max_finish: int) -> float:
        sub = [r for r in past if pred(r) and _finish(r) is not None]
        if not sub:
            return 0.0
        return sum(1 for r in sub if (_finish(r) or 99) <= max_finish) / len(sub)

    def _same_jyo(r: dict) -> bool:
        return str(r.get("JyoCD") or "") == jyo and jyo != ""

    def _same_dist(r: dict) -> bool:
        return bool(band) and distance_band(int(r.get("Kyori") or r.get("distance") or 0)) == band

    def _same_track(r: dict) -> bool:
        return track != "" and str(r.get("TrackCD") or r.get("track") or "") == track
    same_jyo = _subset_rate(_same_jyo, 1)
    same_dist = _subset_rate(_same_dist, 1)
    same_track = _subset_rate(_same_track, 1)
    same_jyo_rentai = _subset_rate(_same_jyo, 2)
    same_dist_rentai = _subset_rate(_same_dist, 2)
    same_track_rentai = _subset_rate(_same_track, 2)
    wop = (win_rate / place_rate) if place_rate > 0 else 0.0

    last = past[-1] if past else {}
    last_dist = int(last.get("Kyori") or last.get("distance") or 0) if last else 0
    dist_delta = float(dist - last_dist) if dist and last_dist else 0.0
    days = _days_between(_date_key(today), _date_key(last)) if last and today.get("Year") else 0.0
    same_track_last = 1.0 if last and track and str(last.get("TrackCD") or "") == track else 0.0
    umaban = _num(today, "Umaban", "umaban") or 0.0
    field_size = float(today.get("field_size") or 0.0)
    weight = _num(last, "BaTaiju", "bataiju", "weight") or 0.0
    zogen = _num(last, "ZogenFugo", "Zogen", "zogen") or 0.0
    # ZogenFugo may be a sign code; use ZogenSa if present
    zogen_sa = _num(last, "ZogenSa", "zogen_sa")
    weight_delta = zogen_sa if zogen_sa is not None else zogen
    futan = _num(today, "Futan", "futan", "burden") or 0.0
    if futan > 70:
        futan = futan / 10.0
    jockey_now = str(today.get("KisyuCode") or today.get("kisyu") or "")
    jockey_last = str(last.get("KisyuCode") or last.get("kisyu") or "") if last else ""
    same_jockey = 1.0 if jockey_now and jockey_now == jockey_last else 0.0
    corners = [
        _num(last, k)
        for k in ("Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c")
        if last
    ]
    corners = [c for c in corners if c is not None]
    last_corner = sum(corners) / len(corners) if corners else 0.0

    vec = np.array(
        [
            n,
            win_rate,
            rentai_rate,
            place_rate,
            inv_avg,
            same_jyo,
            same_dist,
            same_track,
            same_jyo_rentai,
            same_dist_rentai,
            same_track_rentai,
            wop,
            days,
            dist_delta,
            same_track_last,
            umaban / 18.0,
            field_size,
            _agari(last) if last else 0.0,
            weight,
            weight_delta,
            futan,
            same_jockey,
            last_corner,
        ],
        dtype=float,
    )
    if len(vec) != len(FEATURE_NAMES):
        raise RuntimeError(f"feature length {len(vec)} != {len(FEATURE_NAMES)}")
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
            row = dict(m)
            row["field_size"] = len(members)
            past = [p for p in by_horse[ketto] if _date_key(p) < race_date and _finish(p)]
            block_x.append(feature_vector(past, row))
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
        merged = {**race, **e, "field_size": len(entries)}
        past = past_by_horse.get(ketto, [])
        rows.append(feature_vector(past, merged if merged.get("JyoCD") else today))
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES)))
    return np.vstack(rows)
