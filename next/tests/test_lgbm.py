from __future__ import annotations

import unittest
from pathlib import Path

from keiba_next.db import connect, detect_schema
from keiba_next.fixture import build_fixture
from keiba_next.lgbm_features import build_training_rows
from keiba_next.lgbm_model import predict_scores, scores_to_win_score, train_ranker, load_ranker


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "out" / "lgbm_fixture.db"
MODEL = ROOT / "out" / "ranker.txt"


class LgbmTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
