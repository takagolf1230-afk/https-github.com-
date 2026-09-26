"""EveryDB2 形の SQLite で、着順・払戻・数値の読み取りが一致するか。"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from keiba_next.db import (
    connect,
    detect_schema,
    fetch_entries,
    fetch_past_runs,
    load_joined_runs,
    verify_db,
)
from keiba_next.jv_values import agari_seconds, futan_kg, weight_delta_kg
from keiba_next.lgbm_features import feature_vector
from keiba_next.lgbm_model import FEATURE_NAMES


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def _build(path: Path, *, payout_umaban: str = "01") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE N_RACE (
          Year TEXT, MonthDay TEXT, JyoCD TEXT, Kaiji TEXT, Nichiji TEXT,
          RaceNum TEXT, Kyori TEXT, TrackCD TEXT, SyussoTosu TEXT, DataKubun TEXT
        );
        CREATE TABLE N_UMA_RACE (
          Year TEXT, MonthDay TEXT, JyoCD TEXT, Kaiji TEXT, Nichiji TEXT, RaceNum TEXT,
          Umaban TEXT, KettoNum TEXT, Bamei TEXT, KakuteiJyuni TEXT, DataKubun TEXT,
          HaronTimeL3 TEXT, BaTaiju TEXT, ZogenFugo TEXT, ZogenSa TEXT, Futan TEXT,
          KisyuCode TEXT, Jyuni4c TEXT, Odds TEXT, IJyoCD TEXT
        );
        CREATE TABLE N_HARAI (
          Year TEXT, MonthDay TEXT, JyoCD TEXT, Kaiji TEXT, Nichiji TEXT, RaceNum TEXT,
          DataKubun TEXT, FuseirituFlag1 TEXT, PayTansyoUmaban1 TEXT, PayTansyoPay1 TEXT
        );
        """
    )
    races = [
        ("2024", "0105", "09", "01", "01", "11", "1600", "1", "03", "7"),
        ("2024", "0105", "09", "01", "01", "12", "1200", "1", "03", "7"),
        ("2023", "1201", "05", "05", "01", "11", "1600", "1", "02", "7"),
    ]
    conn.executemany("INSERT INTO N_RACE VALUES (?,?,?,?,?,?,?,?,?,?)", races)
    horses = [
        # 出馬表と月曜確定が両方ある。確定の1着を残す。
        ("2024", "0105", "09", "01", "01", "11", "01", "K000000001", "アルファ", "00", "2",
         "000", "000", " ", "000", "560", "00600", "00", "0000", "0"),
        ("2024", "0105", "09", "01", "01", "11", "01", "K000000001", "アルファ", "01", "7",
         "348", "480", "-", "004", "560", "00600", "03", "0156", "0"),
        ("2024", "0105", "09", "01", "01", "11", "02", "K000000002", "ブラボー", "02", "7",
         "351", "466", "+", "002", "540", "01000", "05", "0085", "0"),
        ("2024", "0105", "09", "01", "01", "11", "03", "K000000003", "チャーリー", "03", "7",
         "360", "500", "+", "000", "570", "01100", "08", "0210", "0"),
        ("2024", "0105", "09", "01", "01", "11", "04", "K000000004", "取消馬", "00", "2",
         "000", "000", " ", "000", "560", "01200", "00", "0000", "1"),
        ("2024", "0105", "09", "01", "01", "12", "01", "K000000011", "デルタ", "02", "7",
         "340", "470", "+", "006", "550", "00600", "04", "0040", "0"),
        ("2024", "0105", "09", "01", "01", "12", "02", "K000000012", "エコー", "01", "7",
         "336", "490", "-", "008", "560", "01000", "02", "0032", "0"),
        ("2024", "0105", "09", "01", "01", "12", "03", "K000000013", "フォック", "03", "7",
         "355", "510", "+", "004", "540", "01100", "06", "0180", "0"),
        # 過去走と、当該日より後の走（過去走に混ざってはいけない）
        ("2023", "1201", "05", "05", "01", "11", "01", "K000000001", "アルファ", "01", "7",
         "345", "476", "+", "002", "560", "00600", "02", "0042", "0"),
        ("2023", "1201", "05", "05", "01", "11", "02", "K000000002", "ブラボー", "04", "7",
         "360", "470", "+", "000", "540", "01000", "07", "0120", "0"),
        ("2024", "0201", "06", "01", "01", "11", "01", "K000000001", "アルファ", "01", "7",
         "999", "480", "+", "000", "560", "00600", "01", "0020", "0"),
        ("2024", "0201", "06", "01", "01", "11", "02", "K000000099", "後の馬", "02", "7",
         "350", "480", "+", "000", "560", "01000", "03", "0080", "0"),
    ]
    conn.executemany(
        "INSERT INTO N_UMA_RACE VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        horses,
    )
    harai = [
        ("2024", "0105", "09", "01", "01", "11", "1", "0", "05", "000000999"),
        ("2024", "0105", "09", "01", "01", "11", "2", "0", payout_umaban, "000000156"),
        ("2024", "0105", "09", "01", "01", "12", "2", "0", "02", "000000032"),
    ]
    conn.executemany("INSERT INTO N_HARAI VALUES (?,?,?,?,?,?,?,?,?,?)", harai)
    conn.commit()
    conn.close()


class VerifyTests(unittest.TestCase):
    def test_verify_matches_finish_and_payout(self) -> None:
        path = OUT / "everydb_verify.db"
        _build(path)
        with connect(path) as conn:
            report = verify_db(conn, sample_races=10)
            entries = fetch_entries(conn, detect_schema(conn), "2024010509010111")
            past = fetch_past_runs(conn, detect_schema(conn), "K000000001", "20240105")
            rows = load_joined_runs(conn, detect_schema(conn))
        self.assertTrue(report["ok"], report["mismatches"])
        self.assertGreaterEqual(report["counts"]["payouts_checked"], 2)
        self.assertEqual(report["sample_winner"]["agari_sec"], 34.8)
        self.assertEqual(report["sample_winner"]["weight_kg"], 480)
        self.assertEqual(report["sample_winner"]["weight_delta_kg"], -4)
        self.assertEqual(report["sample_winner"]["futan_kg"], 56.0)
        self.assertEqual(report["sample_winner"]["data_kubun"], "7")
        self.assertEqual(sorted(e["Umaban"] for e in entries), ["01", "02", "03"])
        self.assertEqual(entries[0]["KakuteiJyuni"], "01")
        self.assertEqual([p["MonthDay"] for p in past], ["1201"])
        same_race = [
            r for r in rows
            if r["KettoNum"] == "K000000001" and str(r["MonthDay"]) in {"0105", "105"}
        ]
        self.assertEqual(len(same_race), 1)
        self.assertEqual(same_race[0]["TanOdds"], 15.6)
        self.assertEqual(same_race[0]["Kyori"], "1600")

    def test_verify_flags_payout_disagreement(self) -> None:
        path = OUT / "everydb_mismatch.db"
        _build(path, payout_umaban="09")
        with connect(path) as conn:
            report = verify_db(conn, sample_races=10)
        self.assertFalse(report["ok"])
        self.assertTrue(any(m["check"] == "winner_payout" for m in report["mismatches"]))

    def test_everydb_prefix_tables(self) -> None:
        path = OUT / "x_race.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE x_UMA_RACE (Year TEXT)")
        conn.execute("CREATE TABLE x_RACE (Year TEXT)")
        conn.execute("CREATE TABLE x_HARAI (Year TEXT)")
        conn.commit()
        conn.close()
        with connect(path) as conn:
            schema = detect_schema(conn)
        self.assertEqual(schema.race, "x_RACE")
        self.assertEqual(schema.uma_race, "x_UMA_RACE")
        self.assertEqual(schema.harai, "x_HARAI")

    def test_jv_numbers_and_missing_agari(self) -> None:
        self.assertEqual(agari_seconds({"HaronTimeL3": "999"}), 0.0)
        self.assertEqual(agari_seconds({"HaronTimeL3": "348"}), 34.8)
        self.assertEqual(weight_delta_kg({"ZogenFugo": "-", "ZogenSa": "004"}), -4)
        self.assertEqual(futan_kg({"Futan": "560"}), 56.0)
        past = [{
            "Year": 2023,
            "MonthDay": 1201,
            "JyoCD": "05",
            "Kyori": 1600,
            "TrackCD": "1",
            "KakuteiJyuni": "01",
            "HaronTimeL3": "999",
            "BaTaiju": "480",
            "ZogenFugo": "-",
            "ZogenSa": "004",
            "KisyuCode": "00000",
            "Jyuni4c": "03",
        }]
        today = {
            "Year": 2024,
            "MonthDay": 105,
            "JyoCD": "09",
            "Kyori": 1800,
            "TrackCD": "1",
            "Umaban": 1,
            "Futan": "560",
            "KisyuCode": "00000",
            "SyussoTosu": "16",
        }
        vec = feature_vector(past, today)
        names = list(FEATURE_NAMES)
        self.assertEqual(float(vec[names.index("last_agari")]), 0.0)
        self.assertEqual(float(vec[names.index("weight_delta")]), -4.0)
        self.assertEqual(float(vec[names.index("futan")]), 56.0)
        self.assertEqual(float(vec[names.index("same_jockey")]), 0.0)
        self.assertEqual(float(vec[names.index("field_size")]), 16.0)
        self.assertEqual(float(vec[names.index("last_corner_pos")]), 3.0)


if __name__ == "__main__":
    unittest.main()
