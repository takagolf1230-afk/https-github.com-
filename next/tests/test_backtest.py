from __future__ import annotations

import unittest
from pathlib import Path

from keiba_next.backtest import run_backtest


def _row(date_md: int, race: int, uma: int, ketto: str, finish: int, kyori: int = 1600) -> dict:
    return {
        "Year": 2026,
        "MonthDay": date_md,
        "JyoCD": "05",
        "Kaiji": "01",
        "Nichiji": "01",
        "RaceNum": race,
        "Umaban": uma,
        "KettoNum": ketto,
        "KakuteiJyuni": str(finish),
        "Kyori": kyori,
        "TrackCD": "1",
    }


class BacktestTests(unittest.TestCase):
    def test_holdout_hit_rate(self) -> None:
        rows = []
        # A always wins, B always second, six dates. Hold out the last two.
        for i, md in enumerate((101, 201, 301, 401, 501, 601)):
            rows.append(_row(md, 1, 1, "A", 1))
            rows.append(_row(md, 1, 2, "B", 2))
        result = run_backtest(rows, "20260501", Path("/tmp/keiba_next_bt.txt"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["n_test"], 2)
        self.assertGreaterEqual(result["top1_hit_rate"], 0.5)
        self.assertIn("pass_hit_rate", result)
        self.assertEqual(result["n_pass"], 2)

    def test_min_gap_skips_uncertain_races(self) -> None:
        rows = []
        for md in (101, 201, 301, 401, 501, 601):
            rows.append(_row(md, 1, 1, "A", 1))
            rows.append(_row(md, 1, 2, "B", 2))
        result = run_backtest(rows, "20260501", Path("/tmp/keiba_next_bt_gap.txt"), min_gap=1e9)
        self.assertTrue(result["ok"])
        self.assertEqual(result["n_test"], 2)
        self.assertEqual(result["n_pass"], 0)
        self.assertEqual(result["pass_hit_rate"], 0.0)
        self.assertTrue(all(not d["taken"] for d in result["details"]))
