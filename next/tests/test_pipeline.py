from __future__ import annotations

import json
import unittest
from pathlib import Path

from keiba_next.db import connect, detect_schema, fetch_entries, fetch_past_runs, fetch_races_on_date, ping
from keiba_next.fixture import build_fixture
from keiba_next.pipeline import predict_race


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "out" / "test_fixture.db"


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_fixture(FIX)

    def test_ping_and_schema(self) -> None:
        info = ping(FIX)
        self.assertTrue(info["ok"])
        self.assertIn("N_RACE", info["tables"])
        with connect(FIX) as conn:
            schema = detect_schema(conn)
            self.assertEqual(schema.race, "N_RACE")
            self.assertEqual(schema.uma_race, "N_UMA_RACE")

    def test_predict_assigns_marks_and_template(self) -> None:
        with connect(FIX) as conn:
            schema = detect_schema(conn)
            races = fetch_races_on_date(conn, schema, "20260921")
            self.assertEqual(len(races), 1)
            race = races[0]
            rid = "2026092109040711"
            entries = fetch_entries(conn, schema, rid)
            self.assertGreaterEqual(len(entries), 5)
            past = {}
            for e in entries:
                k = e["KettoNum"]
                past[k] = fetch_past_runs(conn, schema, k, "20260921")
            pred = predict_race(race, entries, past, race_id=rid, odds_lookup={(1, 4): 2.8, (1, 8): 21.8})
            d = pred.to_dict()
            self.assertEqual(d["marked"][0]["mark"], "◎")
            self.assertIn(d["pattern"]["name"], {"Solid", "AxisEdge", "Mid", "Chaos"})
            self.assertIn(d["gate"]["action"], {"buy", "skip", "T7"})
            # axis horse should be H001 / umaban 1 given fixture
            self.assertEqual(d["marked"][0]["Umaban"], 1)


if __name__ == "__main__":
    unittest.main()
