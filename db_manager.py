"""SQLite (duty_roster.db) の操作モジュール。

マスタ（スタッフ・シフト種別・必要人数・ルール・月別公休数・特別日）、
希望休/個別予定、勤務表（シフト結果）の読み書きを担当する。
日付は ISO 文字列 (YYYY-MM-DD)、対象月は "YYYY-MM" で扱う。
"""
from __future__ import annotations

import calendar
import datetime as dt
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).with_name("duty_roster.db")

# システムが意味を持って扱う基本シフト（コード変更・削除不可）
CORE_CODES = ["日", "PB", "早", "ハ", "半", "休"]

DAY_TYPES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "holiday", "third_sun"]
DAY_TYPE_LABELS = {
    "mon": "月曜", "tue": "火曜", "wed": "水曜", "thu": "木曜", "fri": "金曜",
    "sat": "土曜", "sun": "日曜", "holiday": "祝日", "third_sun": "第3日曜(特別)",
}

# (code, name, start_time, unit, is_off, is_request, auto_assign, color, sort_order)
DEFAULT_SHIFT_TYPES = [
    ("日", "通常日勤", "08:30", "全日", 0, 0, 1, "#FFFFFF", 10),
    ("PB", "PB(夜当番)", "08:30", "全日", 0, 0, 1, "#FFD966", 20),
    ("早", "早番", "07:30", "全日", 0, 0, 1, "#BDD7EE", 30),
    ("ハ", "ハ番", "08:00", "全日", 0, 0, 1, "#C6E0B4", 40),
    ("半", "半休", "08:30", "半日", 0, 0, 0, "#F8CBAD", 50),
    ("休", "公休", "", "休", 1, 0, 1, "#D9D9D9", 60),
    ("希", "希望休", "", "休", 1, 1, 0, "#E4DFEC", 70),
    ("出", "出張", "", "全日", 0, 1, 0, "#FFE699", 80),
    ("研", "研修", "", "全日", 0, 1, 0, "#DDEBF7", 90),
]

# 必要人数の初期値: day_type -> {shift: (min, max or None)}
_WEEKDAY_HA = {"mon": 2, "tue": 2, "wed": 0, "thu": 2, "fri": 0, "sat": 2, "sun": 0, "holiday": 0, "third_sun": 1}
_EARLY = {"mon": 1, "tue": 1, "wed": 1, "thu": 1, "fri": 1, "sat": 1, "sun": 0, "holiday": 1, "third_sun": 1}
_DAY_MIN = {"mon": 3, "tue": 3, "wed": 3, "thu": 3, "fri": 3, "sat": 2, "sun": 1, "holiday": 1, "third_sun": 1}
_DAY_MAX = {"sat": 4, "sun": 3, "holiday": 3, "third_sun": 3}

# key, value, description
DEFAULT_RULES = [
    ("pb_next_early", 1, "PB翌日は早番にする"),
    ("sat_pb_next_half", 1, "土曜PBの翌日(日曜)は半休にする(PB翌日ルールより優先)"),
    ("max_consecutive_days", 6, "連続勤務の上限日数(これを超える連続勤務を禁止。6=7連勤以上NG)"),
    ("third_sunday_enabled", 1, "第3日曜日の特別ルールを使う"),
    ("holiday_rule_enabled", 1, "祝日用の必要人数(ハ番なし等)を使う"),
]

SAMPLE_STAFF = [
    ("技師A", "常勤", 1, 1, 1), ("技師B", "常勤", 1, 1, 1), ("技師C", "常勤", 1, 1, 1),
    ("技師D", "常勤", 1, 1, 1), ("技師E", "常勤", 1, 1, 1), ("技師F", "常勤", 1, 1, 1),
    ("技師G", "常勤", 1, 1, 1), ("技師H", "常勤", 0, 1, 1), ("技師I", "常勤", 0, 1, 1),
    ("技師J", "常勤", 0, 1, 1), ("技師K", "常勤", 0, 1, 1), ("技師L", "常勤", 0, 1, 1),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    employment TEXT NOT NULL DEFAULT '常勤',
    can_pb INTEGER NOT NULL DEFAULT 1,
    can_early INTEGER NOT NULL DEFAULT 1,
    can_ha INTEGER NOT NULL DEFAULT 1,
    holiday_adjust INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS shift_types (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '全日',
    is_off INTEGER NOT NULL DEFAULT 0,
    is_request INTEGER NOT NULL DEFAULT 0,
    auto_assign INTEGER NOT NULL DEFAULT 0,
    color TEXT NOT NULL DEFAULT '#FFFFFF',
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS requirements (
    day_type TEXT NOT NULL,
    shift_code TEXT NOT NULL,
    min_count INTEGER NOT NULL DEFAULT 0,
    max_count INTEGER,
    PRIMARY KEY (day_type, shift_code)
);
CREATE TABLE IF NOT EXISTS rules (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS monthly_settings (
    ym TEXT PRIMARY KEY,
    holidays INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS special_days (
    date TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    is_holiday INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS requests (
    staff_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    PRIMARY KEY (staff_id, date)
);
CREATE TABLE IF NOT EXISTS roster (
    staff_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    PRIMARY KEY (staff_id, date)
);
CREATE TABLE IF NOT EXISTS roster_meta (
    ym TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""


@contextmanager
def connect(path: Path | str = DB_PATH):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def ym_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _month_range(year: int, month: int) -> tuple[str, str]:
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def init_db() -> None:
    """テーブル作成と初期マスタ投入（空の場合のみ）。"""
    with connect() as con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM shift_types").fetchone()[0] == 0:
            con.executemany("INSERT INTO shift_types VALUES (?,?,?,?,?,?,?,?,?)", DEFAULT_SHIFT_TYPES)
        if con.execute("SELECT COUNT(*) FROM requirements").fetchone()[0] == 0:
            rows = []
            for t in DAY_TYPES:
                rows.append((t, "PB", 1, 1))
                rows.append((t, "早", _EARLY[t], _EARLY[t]))
                rows.append((t, "ハ", _WEEKDAY_HA[t], _WEEKDAY_HA[t]))
                rows.append((t, "日", _DAY_MIN[t], _DAY_MAX.get(t)))
            con.executemany("INSERT INTO requirements VALUES (?,?,?,?)", rows)
        for key, value, desc in DEFAULT_RULES:
            con.execute("INSERT OR IGNORE INTO rules VALUES (?,?,?)", (key, value, desc))


# ---------------------------------------------------------------- staff
STAFF_COLS = ["id", "name", "employment", "can_pb", "can_early", "can_ha", "holiday_adjust", "sort_order", "active"]


def get_staff(active_only: bool = True) -> pd.DataFrame:
    sql = "SELECT * FROM staff" + (" WHERE active=1" if active_only else "") + " ORDER BY sort_order, id"
    with connect() as con:
        df = pd.read_sql_query(sql, con)
    for c in ("can_pb", "can_early", "can_ha", "active"):
        df[c] = df[c].astype(bool)
    return df[STAFF_COLS]


def save_staff(df: pd.DataFrame) -> None:
    """data_editor の結果で上書き保存する。id 欠損=新規、画面から消えた行=削除。"""
    df = df.copy()
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df = df[df["name"] != ""]
    if df["name"].duplicated().any():
        raise ValueError("スタッフ名が重複しています")
    df = df.fillna({"employment": "常勤", "can_pb": True, "can_early": True, "can_ha": True,
                    "holiday_adjust": 0, "active": True})
    with connect() as con:
        keep = []
        for i, r in enumerate(df.itertuples(index=False)):
            vals = (
                r.name, (r.employment or "常勤"), int(bool(r.can_pb)), int(bool(r.can_early)),
                int(bool(r.can_ha)), int(r.holiday_adjust or 0), i, int(bool(r.active)),
            )
            if pd.isna(r.id):
                cur = con.execute(
                    "INSERT INTO staff (name,employment,can_pb,can_early,can_ha,holiday_adjust,sort_order,active)"
                    " VALUES (?,?,?,?,?,?,?,?)", vals)
                keep.append(cur.lastrowid)
            else:
                con.execute(
                    "UPDATE staff SET name=?,employment=?,can_pb=?,can_early=?,can_ha=?,holiday_adjust=?,"
                    "sort_order=?,active=? WHERE id=?", vals + (int(r.id),))
                keep.append(int(r.id))
        existing = [row[0] for row in con.execute("SELECT id FROM staff")]
        for sid in existing:
            if sid not in keep:
                con.execute("DELETE FROM staff WHERE id=?", (sid,))
                con.execute("DELETE FROM requests WHERE staff_id=?", (sid,))
                con.execute("DELETE FROM roster WHERE staff_id=?", (sid,))


def add_sample_staff() -> None:
    with connect() as con:
        for i, (name, emp, pb, early, ha) in enumerate(SAMPLE_STAFF):
            con.execute(
                "INSERT OR IGNORE INTO staff (name,employment,can_pb,can_early,can_ha,sort_order) VALUES (?,?,?,?,?,?)",
                (name, emp, pb, early, ha, i))


# ---------------------------------------------------------------- shift types
SHIFT_COLS = ["code", "name", "start_time", "unit", "is_off", "is_request", "auto_assign", "color", "sort_order"]


def get_shift_types() -> pd.DataFrame:
    with connect() as con:
        df = pd.read_sql_query("SELECT * FROM shift_types ORDER BY sort_order, code", con)
    for c in ("is_off", "is_request", "auto_assign"):
        df[c] = df[c].astype(bool)
    return df[SHIFT_COLS]


def save_shift_types(df: pd.DataFrame) -> None:
    df = df.copy()
    df["code"] = df["code"].fillna("").astype(str).str.strip()
    df = df[df["code"] != ""]
    if df["code"].duplicated().any():
        raise ValueError("シフトの略称が重複しています")
    df = df.fillna({"name": "", "start_time": "", "unit": "全日", "is_off": False, "is_request": False,
                    "auto_assign": False, "color": "#FFFFFF"})
    missing = [c for c in CORE_CODES if c not in set(df["code"])]
    if missing:
        raise ValueError(f"基本シフト({', '.join(missing)})は削除できません")
    with connect() as con:
        for i, r in enumerate(df.itertuples(index=False)):
            con.execute(
                "INSERT INTO shift_types VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET "
                "name=excluded.name,start_time=excluded.start_time,unit=excluded.unit,is_off=excluded.is_off,"
                "is_request=excluded.is_request,auto_assign=excluded.auto_assign,color=excluded.color,"
                "sort_order=excluded.sort_order",
                (r.code, r.name or r.code, r.start_time or "", r.unit or "全日",
                 int(bool(r.is_off)), int(bool(r.is_request)), int(bool(r.auto_assign)),
                 r.color or "#FFFFFF", (i + 1) * 10))
        for (code,) in con.execute("SELECT code FROM shift_types").fetchall():
            if code not in set(df["code"]):
                con.execute("DELETE FROM shift_types WHERE code=?", (code,))


# ---------------------------------------------------------------- requirements / rules
def get_requirements() -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query("SELECT * FROM requirements", con)


def save_requirements(df: pd.DataFrame) -> None:
    with connect() as con:
        con.execute("DELETE FROM requirements")
        for r in df.itertuples(index=False):
            mx = None if pd.isna(r.max_count) else int(r.max_count)
            con.execute("INSERT INTO requirements VALUES (?,?,?,?)",
                        (r.day_type, r.shift_code, int(r.min_count or 0), mx))


def get_rules() -> dict[str, int]:
    with connect() as con:
        return {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM rules")}


def get_rules_df() -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query("SELECT * FROM rules", con)


def set_rule(key: str, value: int) -> None:
    with connect() as con:
        con.execute("UPDATE rules SET value=? WHERE key=?", (int(value), key))


# ---------------------------------------------------------------- monthly / special days
def get_monthly_holidays(ym: str) -> int | None:
    with connect() as con:
        row = con.execute("SELECT holidays FROM monthly_settings WHERE ym=?", (ym,)).fetchone()
    return None if row is None else int(row[0])


def set_monthly_holidays(ym: str, holidays: int) -> None:
    with connect() as con:
        con.execute("INSERT INTO monthly_settings VALUES (?,?) ON CONFLICT(ym) DO UPDATE SET holidays=excluded.holidays",
                    (ym, int(holidays)))


def get_all_monthly_holidays() -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query("SELECT ym, holidays FROM monthly_settings ORDER BY ym", con)


def get_special_days() -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query("SELECT date, name, is_holiday FROM special_days ORDER BY date", con)


def save_special_days(df: pd.DataFrame) -> None:
    with connect() as con:
        con.execute("DELETE FROM special_days")
        for r in df.itertuples(index=False):
            if r.date is None or pd.isna(r.date):
                continue
            d = pd.to_datetime(r.date).date().isoformat()
            con.execute("INSERT OR REPLACE INTO special_days VALUES (?,?,?)",
                        (d, r.name if isinstance(r.name, str) else "", int(bool(r.is_holiday))))


# ---------------------------------------------------------------- requests (希望休など)
def get_requests(year: int, month: int) -> dict[tuple[int, int], str]:
    """{(staff_id, day): code}"""
    s, e = _month_range(year, month)
    with connect() as con:
        rows = con.execute("SELECT staff_id,date,code FROM requests WHERE date BETWEEN ? AND ?", (s, e)).fetchall()
    return {(r["staff_id"], int(r["date"][-2:])): r["code"] for r in rows}


def save_requests(year: int, month: int, reqs: dict[tuple[int, int], str]) -> None:
    s, e = _month_range(year, month)
    with connect() as con:
        con.execute("DELETE FROM requests WHERE date BETWEEN ? AND ?", (s, e))
        con.executemany(
            "INSERT INTO requests VALUES (?,?,?)",
            [(sid, f"{year:04d}-{month:02d}-{d:02d}", code) for (sid, d), code in reqs.items() if code])


# ---------------------------------------------------------------- roster
def roster_exists(year: int, month: int) -> bool:
    with connect() as con:
        return con.execute("SELECT 1 FROM roster_meta WHERE ym=?", (ym_str(year, month),)).fetchone() is not None


def get_roster(year: int, month: int) -> dict[int, dict[int, str]]:
    s, e = _month_range(year, month)
    out: dict[int, dict[int, str]] = {}
    with connect() as con:
        for r in con.execute("SELECT staff_id,date,code FROM roster WHERE date BETWEEN ? AND ?", (s, e)):
            out.setdefault(r["staff_id"], {})[int(r["date"][-2:])] = r["code"]
    return out


def save_roster(year: int, month: int, roster: dict[int, dict[int, str]], note: str = "") -> None:
    s, e = _month_range(year, month)
    with connect() as con:
        con.execute("DELETE FROM roster WHERE date BETWEEN ? AND ?", (s, e))
        con.executemany(
            "INSERT INTO roster VALUES (?,?,?)",
            [(sid, f"{year:04d}-{month:02d}-{d:02d}", c) for sid, days in roster.items() for d, c in days.items() if c])
        con.execute(
            "INSERT INTO roster_meta VALUES (?,?,?) ON CONFLICT(ym) DO UPDATE SET updated_at=excluded.updated_at,note=excluded.note",
            (ym_str(year, month), dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), note))


def delete_roster(year: int, month: int) -> None:
    s, e = _month_range(year, month)
    with connect() as con:
        con.execute("DELETE FROM roster WHERE date BETWEEN ? AND ?", (s, e))
        con.execute("DELETE FROM roster_meta WHERE ym=?", (ym_str(year, month),))


def get_prev_tail(year: int, month: int, n: int = 7) -> dict[int, dict[int, str]]:
    """前月末 n 日分の勤務。{staff_id: {k: code}} (k=1 が前月最終日、2 がその前日…)"""
    first = dt.date(year, month, 1)
    start = first - dt.timedelta(days=n)
    end = first - dt.timedelta(days=1)
    out: dict[int, dict[int, str]] = {}
    with connect() as con:
        rows = con.execute("SELECT staff_id,date,code FROM roster WHERE date BETWEEN ? AND ?",
                           (start.isoformat(), end.isoformat())).fetchall()
    for r in rows:
        k = (first - dt.date.fromisoformat(r["date"])).days
        out.setdefault(r["staff_id"], {})[k] = r["code"]
    return out
