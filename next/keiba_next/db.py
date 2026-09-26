"""JRA公式 DB（jv_data.db 等）への読み取り専用アクセス。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .jv_values import (
    SE_RESULT_KUBUN,
    canonical_row,
    date_key,
    finish_place,
    hr_kubun_rank,
    is_scratched,
    norm_code,
    se_kubun_rank,
    tan_odds,
    tansyo_umabans,
    agari_seconds,
    body_weight_kg,
    futan_kg,
    weight_delta_kg,
)


def resolve_db_path(db: str | Path) -> Path:
    path = Path(db).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"JRA DB not found: {path}. Pass --db /path/to/jv_data.db"
        )
    return path


def connect(db: str | Path) -> sqlite3.Connection:
    path = resolve_db_path(db)
    # Windows の C:\... も読める URI。mode=ro で書き込まない。
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
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


def find_col(columns: Iterable[str], *candidates: str) -> str | None:
    lower = {c.lower(): c for c in columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _pick(
    tables: Iterable[str],
    *candidates: str,
    reject: tuple[str, ...] = (),
) -> str | None:
    lower = {t.lower(): t for t in tables}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    for c in candidates:
        for name, orig in lower.items():
            if any(token in name for token in reject):
                continue
            if name == c.lower() or name.endswith("_" + c.lower()) or name.endswith(c.lower()):
                return orig
    return None


def detect_schema(conn: sqlite3.Connection) -> SchemaMap:
    tables = list_tables(conn)
    race = _pick(
        tables,
        "N_RACE",
        "x_RACE",
        "RACE",
        "jv_race",
        reject=("uma", "harai", "odds", "toku"),
    )
    uma = _pick(
        tables,
        "N_UMA_RACE",
        "x_UMA_RACE",
        "UMA_RACE",
        "jv_uma_race",
        reject=("harai", "odds"),
    )
    if not race or not uma:
        raise RuntimeError(
            "Required tables not found (need race + uma_race). "
            f"tables={tables[:40]}{'...' if len(tables) > 40 else ''}"
        )
    return SchemaMap(
        race=race,
        uma_race=uma,
        harai=_pick(tables, "N_HARAI", "x_HARAI", "HARAI", "payoff", reject=("uma", "odds")),
        odds_tan=_pick(tables, "ODDS_TANPUKU", "N_ODDS_TANPUKU", "odds_tanpuku", "odds_win"),
        odds_wide=_pick(tables, "ODDS_WIDE", "N_ODDS_WIDE", "odds_wide"),
        odds_umaren=_pick(tables, "ODDS_UMAREN", "N_ODDS_UMAREN", "odds_umaren"),
        odds_sanren=_pick(tables, "ODDS_SANREN", "N_ODDS_SANREN", "odds_sanren"),
        odds_sanrentan=_pick(
            tables, "ODDS_SANRENTAN", "N_ODDS_SANRENTAN", "odds_sanrentan"
        ),
    )


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [canonical_row(dict(r)) for r in conn.execute(sql, params).fetchall()]


def _date_expr(year_col: str, month_col: str) -> str:
    return (
        f"printf('%04d%04d', CAST(\"{year_col}\" AS INTEGER), "
        f"CAST(\"{month_col}\" AS INTEGER))"
    )


def _race_key_sql(columns: Iterable[str], alias: str = "") -> tuple[str, list[str]]:
    """YYYYMMDD + 場2 + 回2 + 日2 + R2 をゼロ埋めで比べる。"""
    prefix = f'{alias}.' if alias else ""
    needed = ("Year", "MonthDay", "JyoCD", "Kaiji", "Nichiji", "RaceNum")
    actual = []
    for name in needed:
        found = find_col(columns, name)
        if not found:
            raise RuntimeError(f"Missing race key column {name}")
        actual.append(found)
    widths = (4, 4, 2, 2, 2, 2)
    parts = [
        f"printf('%0{width}d', CAST({prefix}\"{col}\" AS INTEGER))"
        for col, width in zip(actual, widths)
    ]
    return " AND ".join(f"{part} = ?" for part in parts), actual


def race_id_parts(race_id: str) -> tuple[str, str, str, str, str, str]:
    if len(race_id) < 16:
        raise ValueError(f"race_id must be 16 chars YYYYMMDDJJRR, got {race_id!r}")
    return (
        race_id[0:4],
        race_id[4:8],
        race_id[8:10],
        race_id[10:12],
        race_id[12:14],
        race_id[14:16],
    )


def horse_key(row: dict) -> tuple:
    ketto = str(row.get("KettoNum") or "").strip()
    if ketto and set(ketto) - {"0"}:
        ident = ketto
    else:
        ident = "u" + norm_code(row.get("Umaban"), 2)
    return (
        date_key(row["Year"], row["MonthDay"]) if row.get("Year") is not None else "",
        norm_code(row.get("JyoCD"), 2),
        norm_code(row.get("Kaiji"), 2),
        norm_code(row.get("Nichiji"), 2),
        norm_code(row.get("RaceNum"), 2),
        ident,
    )


def dedupe_uma_rows(rows: list[dict]) -> list[dict]:
    """同じ馬・同じレースの速報と確定が並ぶときは、確定側を残す。"""
    chosen: dict[tuple, dict] = {}
    for row in rows:
        if str(row.get("DataKubun") or "").strip() in {"0", "9"}:
            continue
        if is_scratched(row) and finish_place(row.get("KakuteiJyuni")) is None:
            continue
        key = horse_key(row)
        current = chosen.get(key)
        if current is None or se_kubun_rank(row.get("DataKubun")) >= se_kubun_rank(
            current.get("DataKubun")
        ):
            chosen[key] = row
    return list(chosen.values())


def fetch_races_on_date(conn: sqlite3.Connection, schema: SchemaMap, yyyymmdd: str) -> list[dict]:
    cols = table_columns(conn, schema.race)
    date_col = find_col(cols, "KaishiBi", "kaisaibi", "HoldDate", "hold_date", "race_date", "YearMonthDay")
    if date_col is None:
        year_col = find_col(cols, "Year")
        month_col = find_col(cols, "MonthDay")
        if year_col and month_col:
            sql = f'''
                SELECT * FROM "{schema.race}"
                WHERE {_date_expr(year_col, month_col)} = ?
                ORDER BY "{find_col(cols, "JyoCD") or year_col}", "{find_col(cols, "RaceNum") or month_col}"
            '''
            return _rows(conn, sql, (yyyymmdd,))
        raise RuntimeError(f"No date column on {schema.race}: {sorted(cols)}")
    sql = f'''
        SELECT * FROM "{schema.race}"
        WHERE CAST("{date_col}" AS TEXT) = ?
        ORDER BY 1
    '''
    return _rows(conn, sql, (yyyymmdd,))


def fetch_entries(
    conn: sqlite3.Connection, schema: SchemaMap, race_id: str
) -> list[dict]:
    cols = table_columns(conn, schema.uma_race)
    id_col = find_col(cols, "race_id", "RaceId", "RaceID", "raceKey", "RaceKey")
    if id_col is None and find_col(cols, "Year") and find_col(cols, "MonthDay"):
        where, _actual = _race_key_sql(cols)
        umaban = find_col(cols, "Umaban")
        order = f'ORDER BY CAST("{umaban}" AS INTEGER)' if umaban else ""
        sql = f'SELECT * FROM "{schema.uma_race}" WHERE {where} {order}'
        rows = dedupe_uma_rows(_rows(conn, sql, race_id_parts(race_id)))
        rows.sort(key=lambda r: int(norm_code(r.get("Umaban"), 2) or 0))
        return rows
    if id_col is None:
        raise RuntimeError(f"Cannot resolve race key columns on {schema.uma_race}")
    sql = f'SELECT * FROM "{schema.uma_race}" WHERE "{id_col}"=? ORDER BY 1'
    return dedupe_uma_rows(_rows(conn, sql, (race_id,)))


def fetch_past_runs(
    conn: sqlite3.Connection,
    schema: SchemaMap,
    ketto_num: str,
    before_yyyymmdd: str,
    limit: int = 10,
) -> list[dict]:
    """当該日前の確定過去走。速報と月曜確定が両方あっても1走にまとめる。"""
    cols = table_columns(conn, schema.uma_race)
    horse_col = find_col(cols, "KettoNum", "ketto_num", "HorseId", "horse_id")
    if horse_col is None:
        raise RuntimeError(f"No horse id column on {schema.uma_race}")
    year_col = find_col(cols, "Year")
    month_col = find_col(cols, "MonthDay")
    finish_col = find_col(cols, "KakuteiJyuni")
    kubun_col = find_col(cols, "DataKubun")
    if year_col and month_col and finish_col:
        kubun_sql = ""
        if kubun_col:
            kubun_sql = (
                f' AND UPPER(TRIM("{kubun_col}")) IN '
                "('7','6','5','4','3','A','B')"
            )
        sql = f'''
            SELECT * FROM "{schema.uma_race}"
            WHERE "{horse_col}" = ?
              AND {_date_expr(year_col, month_col)} < ?
              AND "{finish_col}" IS NOT NULL
              AND CAST("{finish_col}" AS INTEGER) BETWEEN 1 AND 18
              {kubun_sql}
            ORDER BY CAST("{year_col}" AS INTEGER) DESC,
                     CAST("{month_col}" AS INTEGER) DESC
        '''
        rows = dedupe_uma_rows(_rows(conn, sql, (ketto_num, before_yyyymmdd)))
        rows.sort(key=lambda r: date_key(r["Year"], r["MonthDay"]), reverse=True)
        return rows[:limit]
    date_col = find_col(cols, "race_date", "KaishiBi", "kaisaibi", "HoldDate")
    if not date_col:
        raise RuntimeError("No date columns for past runs")
    sql = f'''
        SELECT * FROM "{schema.uma_race}"
        WHERE "{horse_col}" = ?
          AND CAST("{date_col}" AS TEXT) < ?
        ORDER BY "{date_col}" DESC
        LIMIT ?
    '''
    return dedupe_uma_rows(_rows(conn, sql, (ketto_num, before_yyyymmdd, limit)))


def load_joined_runs(conn: sqlite3.Connection, schema: SchemaMap) -> list[dict]:
    """学習・バックテスト用。確定着順がある走だけ。同一馬の重複は落とす。"""
    uma_cols = table_columns(conn, schema.uma_race)
    race_cols = table_columns(conn, schema.race)
    finish_col = find_col(uma_cols, "KakuteiJyuni")
    kubun_col = find_col(uma_cols, "DataKubun")
    if not finish_col:
        raise RuntimeError(f"No finish column on {schema.uma_race}")
    where = [f'CAST(u."{finish_col}" AS INTEGER) BETWEEN 1 AND 18']
    if kubun_col:
        where.append(
            f'''UPPER(TRIM(u."{kubun_col}")) IN ('7','6','5','4','3','A','B')'''
        )
    extras = []
    for name in ("Kyori", "TrackCD", "SyussoTosu"):
        col = find_col(race_cols, name)
        if col:
            extras.append(f'r."{col}" AS "{name}"')
    extra_sql = (", " + ", ".join(extras)) if extras else ""
    join_parts = []
    for name in ("Year", "MonthDay", "JyoCD", "Kaiji", "Nichiji", "RaceNum"):
        u_col = find_col(uma_cols, name)
        r_col = find_col(race_cols, name)
        if not u_col or not r_col:
            raise RuntimeError(f"Cannot join on {name}")
        width = 4 if name in {"Year", "MonthDay"} else 2
        join_parts.append(
            f"printf('%0{width}d', CAST(u.\"{u_col}\" AS INTEGER)) = "
            f"printf('%0{width}d', CAST(r.\"{r_col}\" AS INTEGER))"
        )
    sql = f'''
        SELECT u.*{extra_sql}
        FROM "{schema.uma_race}" u
        JOIN "{schema.race}" r ON {" AND ".join(join_parts)}
        WHERE {" AND ".join(where)}
    '''
    rows = dedupe_uma_rows(_rows(conn, sql))
    for row in rows:
        odds = tan_odds(row)
        if odds is not None and row.get("TanOdds") in (None, ""):
            row["TanOdds"] = odds
    return rows


def _column_coverage(columns: list[str], expected: list[str]) -> dict[str, list[str]]:
    present = []
    missing = []
    for name in expected:
        if find_col(columns, name):
            present.append(name)
        else:
            missing.append(name)
    return {"present": present, "missing": missing}


def _sample_dates(conn: sqlite3.Connection, schema: SchemaMap, limit: int) -> list[str]:
    cols = table_columns(conn, schema.uma_race)
    year_col = find_col(cols, "Year")
    month_col = find_col(cols, "MonthDay")
    finish_col = find_col(cols, "KakuteiJyuni")
    if not (year_col and month_col and finish_col):
        return []
    sql = f'''
        SELECT {_date_expr(year_col, month_col)} AS d
        FROM "{schema.uma_race}"
        WHERE CAST("{finish_col}" AS INTEGER) = 1
        GROUP BY d
        ORDER BY d DESC
        LIMIT ?
    '''
    return [r[0] for r in conn.execute(sql, (limit,)).fetchall()]


def fetch_harai(conn: sqlite3.Connection, schema: SchemaMap, race_id: str) -> dict | None:
    if not schema.harai:
        return None
    cols = table_columns(conn, schema.harai)
    if not find_col(cols, "Year"):
        return None
    where, _ = _race_key_sql(cols)
    rows = _rows(conn, f'SELECT * FROM "{schema.harai}" WHERE {where}', race_id_parts(race_id))
    rows = [r for r in rows if str(r.get("DataKubun") or "").strip() not in {"0", "9"}]
    if not rows:
        return None
    rows.sort(key=lambda r: hr_kubun_rank(r.get("DataKubun")), reverse=True)
    return rows[0]


def verify_db(conn: sqlite3.Connection, sample_races: int = 20) -> dict[str, Any]:
    """接続できたかと、着順・払戻・過去走の取り違えが無いかを照合する。"""
    schema = detect_schema(conn)
    race_cols = table_columns(conn, schema.race)
    uma_cols = table_columns(conn, schema.uma_race)
    n_race = conn.execute(f'SELECT COUNT(*) FROM "{schema.race}"').fetchone()[0]
    n_uma = conn.execute(f'SELECT COUNT(*) FROM "{schema.uma_race}"').fetchone()[0]
    mismatches: list[dict[str, Any]] = []
    checked = 0
    payout_checked = 0
    sample: dict[str, Any] | None = None
    dates = _sample_dates(conn, schema, limit=3)

    for yyyymmdd in dates:
        races = fetch_races_on_date(conn, schema, yyyymmdd)
        for race in races:
            if checked >= sample_races:
                break
            try:
                rid = (
                    f"{int(race['Year']):04d}{int(race['MonthDay']):04d}"
                    f"{norm_code(race.get('JyoCD'), 2)}{norm_code(race.get('Kaiji'), 2)}"
                    f"{norm_code(race.get('Nichiji'), 2)}{norm_code(race.get('RaceNum'), 2)}"
                )
            except (KeyError, TypeError, ValueError):
                mismatches.append({"check": "race_key", "detail": "race key is not numeric"})
                continue
            entries = fetch_entries(conn, schema, rid)
            finished = [e for e in entries if finish_place(e.get("KakuteiJyuni"))]
            if len(finished) < 2:
                continue
            umabans = [int(norm_code(e.get("Umaban"), 2)) for e in finished]
            if len(umabans) != len(set(umabans)):
                mismatches.append({"check": "duplicate_horse", "race_id": rid})
            winners = [e for e in finished if finish_place(e.get("KakuteiJyuni")) == 1]
            if len(winners) < 1:
                mismatches.append({"check": "no_winner", "race_id": rid})
            if schema.harai:
                payoff = fetch_harai(conn, schema, rid)
                if payoff and str(payoff.get("FuseirituFlag1") or "").strip() != "1":
                    paid = tansyo_umabans(payoff)
                    if paid:
                        payout_checked += 1
                        winner_nums = {int(norm_code(e.get("Umaban"), 2)) for e in winners}
                        if not winner_nums <= set(paid):
                            mismatches.append(
                                {
                                    "check": "winner_payout",
                                    "race_id": rid,
                                    "finish_umabans": sorted(winner_nums),
                                    "payout_umabans": paid,
                                }
                            )
            if winners:
                ketto = str(winners[0].get("KettoNum") or "")
                if ketto:
                    past = fetch_past_runs(conn, schema, ketto, yyyymmdd, limit=5)
                    leaked = [
                        p
                        for p in past
                        if date_key(p["Year"], p["MonthDay"]) >= yyyymmdd
                    ]
                    if leaked:
                        mismatches.append({"check": "past_run_leak", "race_id": rid, "n": len(leaked)})
            if sample is None and winners:
                horse = winners[0]
                sample = {
                    "race_id": rid,
                    "bamei": horse.get("Bamei"),
                    "umaban": norm_code(horse.get("Umaban"), 2),
                    "finish": finish_place(horse.get("KakuteiJyuni")),
                    "agari_raw": horse.get("HaronTimeL3"),
                    "agari_sec": agari_seconds(horse),
                    "weight_kg": body_weight_kg(horse),
                    "weight_delta_kg": weight_delta_kg(horse),
                    "futan_kg": futan_kg(horse),
                    "data_kubun": horse.get("DataKubun"),
                }
                agari = sample["agari_sec"]
                weight = sample["weight_kg"]
                burden = sample["futan_kg"]
                if agari and not 10 <= agari <= 50:
                    mismatches.append({"check": "agari_range", "race_id": rid, "agari_sec": agari})
                if weight and not 300 <= weight <= 600:
                    mismatches.append({"check": "weight_range", "race_id": rid, "weight_kg": weight})
                if burden and not 48 <= burden <= 64:
                    mismatches.append({"check": "futan_range", "race_id": rid, "futan_kg": burden})
            checked += 1
        if checked >= sample_races:
            break

    if checked == 0:
        mismatches.append({"check": "no_finished_race", "detail": "確定着順のあるレースを読めなかった"})

    coverage_uma = _column_coverage(
        uma_cols,
        [
            "KettoNum",
            "Umaban",
            "KakuteiJyuni",
            "DataKubun",
            "HaronTimeL3",
            "BaTaiju",
            "ZogenSa",
            "ZogenFugo",
            "Futan",
            "KisyuCode",
            "Jyuni1c",
            "Jyuni4c",
            "IJyoCD",
        ],
    )
    coverage_race = _column_coverage(
        race_cols, ["Year", "MonthDay", "JyoCD", "Kyori", "TrackCD", "SyussoTosu"]
    )
    return {
        "ok": not mismatches,
        "schema": schema.__dict__,
        "counts": {"races": n_race, "uma_rows": n_uma, "races_checked": checked, "payouts_checked": payout_checked},
        "columns": {"race": coverage_race, "uma_race": coverage_uma},
        "sample_winner": sample,
        "mismatches": mismatches,
        "result_kubun": sorted(SE_RESULT_KUBUN),
    }
