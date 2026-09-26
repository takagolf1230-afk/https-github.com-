from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from keiba_next.db import connect, detect_schema
from keiba_next.fixture import build_fixture
from keiba_next.lgbm_features import build_training_rows, feature_vector
from keiba_next.lgbm_model import (
    FEATURE_NAMES,
    predict_scores,
    relevance,
    scores_to_win_score,
    train_ranker,
    load_ranker,
)


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "out" / "lgbm_fixture.db"
MODEL = ROOT / "out" / "ranker.txt"


class LgbmTests(unittest.TestCase):
    def test_relevance_is_win_only(self) -> None:
        self.assertEqual(relevance(1), 1)
        self.assertEqual(relevance(2), 0)
        self.assertEqual(relevance(3), 0)

    def test_train_and_score_shape(self) -> None:
        build_fixture(FIX)
        with connect(FIX) as conn:
            schema = detect_schema(conn)
            sql = f'''
                SELECT u.*, r.Kyori FROM "{schema.uma_race}" u
                JOIN "{schema.race}" r
                  ON u.Year=r.Year AND u.MonthDay=r.MonthDay AND u.JyoCD=r.JyoCD
                 AND u.Kaiji=r.Kaiji AND u.Nichiji=r.Nichiji AND u.RaceNum=r.RaceNum
                WHERE u.KakuteiJyuni IS NOT NULL
            '''
            rows = [dict(r) for r in conn.execute(sql)]
        x, y, group = build_training_rows(rows)
        self.assertGreaterEqual(len(group), 1)
        self.assertEqual(sum(group), len(y))
        path = train_ranker(x, y, group, MODEL)
        model = load_ranker(path)
        scores = predict_scores(model, x[: group[0]])
        norm = scores_to_win_score(scores)
        self.assertEqual(len(norm), group[0])
        self.assertGreaterEqual(float(norm.max()), 50.0)
        self.assertEqual(x.shape[1], len(FEATURE_NAMES))

    def test_non_finish_factors_change_the_vector(self) -> None:
        past = [
            {
                "Year": 2026,
                "MonthDay": 101,
                "JyoCD": "05",
                "Kyori": 1600,
                "TrackCD": "1",
                "KakuteiJyuni": "1",
                "HaronTimeL3": 340,
                "BaTaiju": 480,
                "KisyuCode": "J1",
                "Jyuni4c": 3,
            }
        ]
        base = {
            "Year": 2026,
            "MonthDay": 601,
            "JyoCD": "05",
            "Kyori": 1600,
            "TrackCD": "1",
            "Umaban": 1,
            "field_size": 10,
            "Futan": 560,
            "KisyuCode": "J1",
        }
        same_jockey = feature_vector(past, base)
        changed = feature_vector(
            past,
            {**base, "KisyuCode": "J2", "Umaban": 18, "Kyori": 2400, "Futan": 580},
        )
        self.assertEqual(len(same_jockey), len(FEATURE_NAMES))
        names = list(FEATURE_NAMES)
        for key in ("n_starts", "win_rate", "place_rate", "last_agari", "last_corner_pos"):
            i = names.index(key)
            self.assertEqual(float(same_jockey[i]), float(changed[i]))
        self.assertFalse(np.allclose(same_jockey, changed))
        self.assertEqual(float(same_jockey[names.index("last_agari")]), 34.0)
        self.assertEqual(float(same_jockey[names.index("same_jockey")]), 1.0)
        self.assertEqual(float(changed[names.index("same_jockey")]), 0.0)
        self.assertNotEqual(
            float(same_jockey[names.index("dist_delta")]),
            float(changed[names.index("dist_delta")]),
        )

    def test_rentai_rate_counts_second_place(self) -> None:
        past = [
            {"Year": 2026, "MonthDay": 101, "JyoCD": "09", "Kyori": 2000, "TrackCD": "1", "KakuteiJyuni": "2"},
            {"Year": 2026, "MonthDay": 201, "JyoCD": "09", "Kyori": 2000, "TrackCD": "1", "KakuteiJyuni": "2"},
            {"Year": 2026, "MonthDay": 301, "JyoCD": "05", "Kyori": 1200, "TrackCD": "2", "KakuteiJyuni": "5"},
        ]
        today = {"Year": 2026, "MonthDay": 601, "JyoCD": "09", "Kyori": 2000, "TrackCD": "1", "Umaban": 1}
        vec = feature_vector(past, today)
        names = list(FEATURE_NAMES)
        self.assertEqual(float(vec[names.index("win_rate")]), 0.0)
        self.assertAlmostEqual(float(vec[names.index("rentai_rate")]), 2 / 3)
        self.assertAlmostEqual(float(vec[names.index("same_jyo_rentai_rate")]), 1.0)
        self.assertEqual(float(vec[names.index("same_jyo_win_rate")]), 0.0)
        self.assertGreater(
            float(vec[names.index("rentai_rate")]),
            float(vec[names.index("win_rate")]),
        )


if __name__ == "__main__":
    unittest.main()
