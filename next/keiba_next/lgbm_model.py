"""LightGBM Ranker。印の決定は数値モデルのみ。オッズは特徴に入れない。"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np

FEATURE_NAMES = (
    "n_starts",
    "win_rate",
    "rentai_rate",
    "place_rate",
    "inv_avg_finish",
    "same_jyo_win_rate",
    "same_dist_win_rate",
    "same_track_win_rate",
    "same_jyo_rentai_rate",
    "same_dist_rentai_rate",
    "same_track_rentai_rate",
    "win_over_place",
    "days_since_last",
    "dist_delta",
    "same_track_last",
    "umaban_norm",
    "field_size",
    "last_agari",
    "last_weight",
    "weight_delta",
    "futan",
    "same_jockey",
    "last_corner_pos",
)


def relevance(finish: int) -> int:
    """一着特化。1着だけ 1、それ以外は 0。"""
    return 1 if finish == 1 else 0


def train_ranker(
    x: np.ndarray,
    y: np.ndarray,
    group: list[int],
    model_path: str | Path,
) -> Path:
    if x.shape[0] != len(y) or sum(group) != len(y):
        raise ValueError("X, y, group size mismatch")
    if any(g < 2 for g in group):
        raise ValueError("each race group needs at least 2 horses")
    train = lgb.Dataset(x, label=y, group=group, feature_name=list(FEATURE_NAMES))
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [1, 3],
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_data_in_leaf": 1,
        "verbose": -1,
    }
    booster = lgb.train(params, train, num_boost_round=40)
    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(path))
    return path


def load_ranker(model_path: str | Path) -> lgb.Booster:
    return lgb.Booster(model_file=str(model_path))


def predict_scores(model: lgb.Booster, x: np.ndarray) -> np.ndarray:
    return np.asarray(model.predict(x), dtype=float)


def scores_to_win_score(scores: np.ndarray) -> np.ndarray:
    """レース内で 0-100 に正規化。"""
    if len(scores) == 0:
        return scores
    lo, hi = float(scores.min()), float(scores.max())
    if hi <= lo:
        return np.full_like(scores, 50.0, dtype=float)
    return (scores - lo) / (hi - lo) * 100.0
