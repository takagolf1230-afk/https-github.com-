"""JRA公式 DB（jv_data.db 等）への読み取り専用アクセス。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def resolve_db_path(db: str | Path) -> Path:
    path = Path(db).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"JRA DB not found: {path}. Pass --db /path/to/jv_data.db"
        )
    return path


def connect(db: str | Path) -> sqlite3.Connection:
    path = resolve_db_path(db)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def ping(db: str | Path) -> dict[str, Any]:
    path = resolve_db_path(db)
    with connect(path) as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
    return {"ok": True, "db": str(path), "size_bytes": path.stat().st_size, "tables": tables}


def list_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


@dataclass(frozen=True)
class SchemaMap:
    """実DBのテーブル名ゆれを吸収する。"""

    race: str
    uma_race: str
    harai: str | None = None
    odds_tan: str | None = None
    odds_wide: str | None = None
    odds_umaren: str | None = None
    odds_sanren: str | None = None
    odds_sanrentan: str | None = None


def _pick(tables: Iterable[str], *candidates: str) -> str | None:
    lower = {t.lower(): t for t in tables}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    # fuzzy contains
    for c in candidates:
        for name, orig in lower.items():
            if c.lower() in name:
                return orig
    return None


def detect_schema(conn: sqlite3.Connection) -> SchemaMap:
    tables = list_tables(conn)
    race = _pick(tables, "N_RACE", "RACE", "race", "jv_race")
    uma = _pick(tables, "N_UMA_RACE", "UMA_RACE", "uma_race", "jv_uma_race")
    if not race or not uma:
        raise RuntimeError(
            "Required tables not found (need race + uma_race). "
            f"tables={tables[:40]}{'...' if len(tables) > 40 else ''}"
        )
    return SchemaMap(
        race=race,
        uma_race=uma,
        harai=_pick(tables, "N_HARAI", "HARAI", "harai", "payoff"),
        odds_tan=_pick(tables, "ODDS_TANPUKU", "N_ODDS_TANPUKU", "odds_tanpuku", "odds_win"),
        odds_wide=_pick(tables, "ODDS_WIDE", "N_ODDS_WIDE", "odds_wide"),
        odds_umaren=_pick(tables, "ODDS_UMAREN", "N_ODDS_UMAREN", "odds_umaren"),
        odds_sanren=_pick(tables, "ODDS_SANREN", "N_ODDS_SANREN", "odds_sanren"),
        odds_sanrentan=_pick(
            tables, "ODDS_SANRENTAN", "N_ODDS_SANRENTAN", "odds_sanrentan"
        ),
    )


def fetch_races_on_date(conn: sqlite3.Connection, schema: SchemaMap, yyyymmdd: str) -> list[dict]:
    cols = set(table_columns(conn, schema.race))
    date_col = next(
        (c for c in ("KaishiBi", "kaisaibi", "HoldDate", "hold_date", "race_date", "YearMonthDay") if c in cols),
        None,
    )
    if date_col is None:
        # concatenated Year+MonthDay style
        if {"Year", "MonthDay"} <= cols:
            sql = f'''
                SELECT * FROM "{schema.race}"
                WHERE printf('%04d%04d', Year, MonthDay) = ?
                ORDER BY JyoCD, RaceNum
            '''
            rows = conn.execute(sql, (yyyymmdd,)).fetchall()
            return [dict(r) for r in rows]
        raise RuntimeError(f"No date column on {schema.race}: {sorted(cols)}")
    sql = f'''
        SELECT * FROM "{schema.race}"
        WHERE CAST("{date_col}" AS TEXT) = ?
        ORDER BY 1
    '''
    return [dict(r) for r in conn.execute(sql, (yyyymmdd,)).fetchall()]


def fetch_entries(
    conn: sqlite3.Connection, schema: SchemaMap, race_id: str
) -> list[dict]:
    cols = set(table_columns(conn, schema.uma_race))
    id_col = next(
        (c for c in ("race_id", "RaceId", "RaceID", "id", "raceKey", "RaceKey") if c in cols),
        None,
    )
    if id_col is None and {"Year", "MonthDay", "JyoCD", "Kaiji", "Nichiji", "RaceNum"} <= cols:
        # race_id encoded as YYYYMMDDJJRR style — caller passes that string
        y, md, jyo, kai, nichi, rnum = (
            race_id[0:4],
            race_id[4:8],
            race_id[8:10],
            race_id[10:12],
            race_id[12:14],
            race_id[14:16],
        )
        sql = f'''
            SELECT * FROM "{schema.uma_race}"
            WHERE Year=? AND MonthDay=? AND JyoCD=? AND Kaiji=? AND Nichiji=? AND RaceNum=?
            ORDER BY Umaban
        '''
        return [
            dict(r)
            for r in conn.execute(sql, (int(y), int(md), jyo, kai, nichi, int(rnum))).fetchall()
        ]
    if id_col is None:
        raise RuntimeError(f"Cannot resolve race key columns on {schema.uma_race}")
    sql = f'SELECT * FROM "{schema.uma_race}" WHERE "{id_col}"=? ORDER BY 1'
    return [dict(r) for r in conn.execute(sql, (race_id,)).fetchall()]


def fetch_past_runs(
    conn: sqlite3.Connection,
    schema: SchemaMap,
    ketto_num: str,
    before_yyyymmdd: str,
    limit: int = 10,
) -> list[dict]:
    """当該日前の過去走（リーク防止）。"""
    cols = set(table_columns(conn, schema.uma_race))
    horse_col = next(
        (c for c in ("KettoNum", "ketto_num", "HorseId", "horse_id", "Bamei") if c in cols),
        None,
    )
    if horse_col is None:
        raise RuntimeError(f"No horse id column on {schema.uma_race}")
    if {"Year", "MonthDay"} <= cols:
        sql = f'''
            SELECT * FROM "{schema.uma_race}"
            WHERE "{horse_col}" = ?
              AND printf('%04d%04d', Year, MonthDay) < ?
              AND KakuteiJyuni IS NOT NULL
              AND CAST(KakuteiJyuni AS INTEGER) BETWEEN 1 AND 18
            ORDER BY Year DESC, MonthDay DESC
            LIMIT ?
        '''
        return [
            dict(r)
            for r in conn.execute(sql, (ketto_num, before_yyyymmdd, limit)).fetchall()
        ]
    date_col = next(
        (c for c in ("race_date", "KaishiBi", "kaisaibi", "HoldDate") if c in cols),
        None,
    )
    if not date_col:
        raise RuntimeError("No date columns for past runs")
    sql = f'''
        SELECT * FROM "{schema.uma_race}"
        WHERE "{horse_col}" = ?
          AND CAST("{date_col}" AS TEXT) < ?
        ORDER BY "{date_col}" DESC
        LIMIT ?
    '''
    return [
        dict(r) for r in conn.execute(sql, (ketto_num, before_yyyymmdd, limit)).fetchall()
    ]
