"""時系列バックテスト。until 未満で学習し、以降のレースで1着的中を測る。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

from .lgbm_features import _date_key, _finish, _race_key, build_predict_matrix, build_training_rows
from .lgbm_model import load_ranker, predict_scores, train_ranker


def _group_races(rows: list[dict]) -> dict[str, list[dict]]:
    races: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if _finish(r) is None:
            continue
        races[_race_key(r)].append(r)
    return races


def run_backtest(rows: list[dict], until: str, model_path: str | Path) -> dict:
    """until (YYYYMMDD) 未満で学習、以降で◎（スコア1位）の単勝的中率を出す。"""
    train_rows = [r for r in rows if _date_key(r) < until and _finish(r) is not None]
    x, y, group = build_training_rows(train_rows)
    if len(y) < 4 or not group:
        return {"ok": False, "error": "not enough train rows", "n_train": int(len(y))}
    train_ranker(x, y, group, model_path)
    model = load_ranker(model_path)

    races = _group_races(rows)
    hits = 0
    n = 0
    stake = 0.0
    ret = 0.0
    details = []
    for key in sorted(races):
        members = races[key]
        if _date_key(members[0]) < until or len(members) < 2:
            continue
        race = members[0]
        past_by: dict[str, list[dict]] = defaultdict(list)
        race_date = _date_key(race)
        for r in rows:
            ketto = str(r.get("KettoNum") or "")
            if ketto and _date_key(r) < race_date and _finish(r) is not None:
                past_by[ketto].append(r)
        matrix = build_predict_matrix(members, past_by, race)
        scores = predict_scores(model, matrix)
        top_i = int(np.argmax(scores))
        top = members[top_i]
        won = _finish(top) == 1
        n += 1
        hits += int(won)
        stake += 100.0
        odds = top.get("TanOdds") or top.get("win_odds")
        if won and odds not in (None, ""):
            ret += 100.0 * float(odds)
        details.append(
            {
                "race": key,
                "umaban": top.get("Umaban"),
                "ketto": top.get("KettoNum"),
                "won": won,
            }
        )
    return {
        "ok": True,
        "until": until,
        "n_test": n,
        "top1_hits": hits,
        "top1_hit_rate": (hits / n) if n else 0.0,
        "stake": stake,
        "return": ret,
        "roi": (ret / stake) if stake and ret else None,
        "details": details,
    }
