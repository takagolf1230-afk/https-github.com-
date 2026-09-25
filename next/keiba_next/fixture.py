"""開発・テスト用の最小 JV 風 SQLite を生成する。"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def build_fixture(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE N_RACE (
          Year INTEGER, MonthDay INTEGER, JyoCD TEXT, Kaiji TEXT, Nichiji TEXT,
          RaceNum INTEGER, Kyori INTEGER, TrackCD TEXT, SibaBabaCD TEXT
        );
        CREATE TABLE N_UMA_RACE (
          Year INTEGER, MonthDay INTEGER, JyoCD TEXT, Kaiji TEXT, Nichiji TEXT,
          RaceNum INTEGER, Umaban INTEGER, KettoNum TEXT, Bamei TEXT,
          KakuteiJyuni TEXT
        );
        CREATE TABLE ODDS_WIDE (
          race_id TEXT, umaban1 INTEGER, umaban2 INTEGER, Odds REAL
        );
        """
    )
    # Target race: 20260921 Hanshin R11, 2400 turf
    cur.execute(
        "INSERT INTO N_RACE VALUES (2026,921,'09','04','07',11,2400,'1','1')"
    )
    # Past races for conditioning
    past_races = [
        (2026, 801, "09", "03", "05", 11, 2400, "1", "1"),
        (2026, 510, "09", "02", "06", 11, 2400, "1", "1"),
        (2025, 1026, "09", "05", "08", 11, 2400, "1", "1"),
    ]
    cur.executemany(
        "INSERT INTO N_RACE VALUES (?,?,?,?,?,?,?,?,?)", past_races
    )

    # Horses: 1=strong win on similar, 4=placey, 8=dark course win, others filler
    entries = [
        (2026, 921, "09", "04", "07", 11, 1, "H001", "ロブチェン", None),
        (2026, 921, "09", "04", "07", 11, 4, "H004", "アルトラムス", None),
        (2026, 921, "09", "04", "07", 11, 8, "H008", "シートゥサミット", None),
        (2026, 921, "09", "04", "07", 11, 2, "H002", "穴馬B", None),
        (2026, 921, "09", "04", "07", 11, 5, "H005", "普通馬C", None),
    ]
    cur.executemany(
        "INSERT INTO N_UMA_RACE VALUES (?,?,?,?,?,?,?,?,?,?)", entries
    )

    # Past results — H001 dominates same course_key (阪神|芝|long|2400)
    past = [
        (2026, 801, "09", "03", "05", 11, 1, "H001", "ロブチェン", "1"),
        (2026, 510, "09", "02", "06", 11, 3, "H001", "ロブチェン", "1"),
        (2025, 1026, "09", "05", "08", 11, 2, "H001", "ロブチェン", "1"),
        # H004 place specialist, rarely wins
        (2026, 801, "09", "03", "05", 11, 4, "H004", "アルトラムス", "3"),
        (2026, 510, "09", "02", "06", 11, 4, "H004", "アルトラムス", "2"),
        (2025, 1026, "09", "05", "08", 11, 4, "H004", "アルトラムス", "3"),
        # H008 one upset win, mostly out — dark candidate
        (2026, 510, "09", "02", "06", 11, 8, "H008", "シートゥサミット", "1"),
        (2026, 801, "09", "03", "05", 11, 8, "H008", "シートゥサミット", "10"),
        (2025, 1026, "09", "05", "08", 11, 8, "H008", "シートゥサミット", "12"),
        (2026, 801, "09", "03", "05", 11, 2, "H002", "穴馬B", "5"),
        (2026, 801, "09", "03", "05", 11, 5, "H005", "普通馬C", "6"),
    ]
    cur.executemany(
        "INSERT INTO N_UMA_RACE VALUES (?,?,?,?,?,?,?,?,?,?)", past
    )

    # Wide odds: 1-4 thin, 1-8 richer
    rid = "202609210911"
    cur.executemany(
        "INSERT INTO ODDS_WIDE VALUES (?,?,?,?)",
        [
            (rid, 1, 4, 2.8),
            (rid, 1, 8, 21.8),
            (rid, 4, 8, 78.0),
            (rid, 1, 2, 12.0),
            (rid, 1, 5, 15.0),
        ],
    )
    conn.commit()
    conn.close()
    return path
