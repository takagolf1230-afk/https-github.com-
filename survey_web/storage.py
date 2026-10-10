"""SQLite への保存。個人を特定する情報(IPアドレス等)は保存しない。メールアドレスは回答と別テーブル。"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).with_name("survey.db")


def db_path() -> str:
    return os.environ.get("SURVEY_DB", str(DEFAULT_DB))


@contextmanager
def connect():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            answers TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        """)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_response(answers: dict, source: str, email: str = "") -> None:
    with connect() as con:
        con.execute("INSERT INTO responses (created_at, source, answers) VALUES (?,?,?)",
                    (now(), source, json.dumps(answers, ensure_ascii=False)))
        if email:
            con.execute("INSERT OR IGNORE INTO leads (created_at, email) VALUES (?,?)", (now(), email))


def all_responses() -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT * FROM responses ORDER BY id").fetchall()
    return [{"id": r["id"], "created_at": r["created_at"], "source": r["source"], **json.loads(r["answers"])} for r in rows]


def all_leads() -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT created_at, email FROM leads ORDER BY id")]


def delete_response(rid: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM responses WHERE id=?", (rid,))
