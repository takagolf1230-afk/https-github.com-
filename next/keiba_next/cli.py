"""CLI: keiba_next 新予想システム。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m keiba_next.cli` from next/
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keiba_next.db import (
    connect,
    detect_schema,
    fetch_entries,
    fetch_past_runs,
    fetch_races_on_date,
    ping,
    table_columns,
)
from keiba_next.fixture import build_fixture
from keiba_next.pipeline import predict_race


def _race_id_from_row(r: dict) -> str:
    if "race_id" in r:
        return str(r["race_id"])
    y = int(r["Year"])
    md = int(r["MonthDay"])
    return f"{y:04d}{md:04d}{r['JyoCD']}{r['Kaiji']}{r['Nichiji']}{int(r['RaceNum']):02d}"


def cmd_ping(args: argparse.Namespace) -> int:
    info = ping(args.db)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        schema = detect_schema(conn)
        out = {
            "schema": schema.__dict__,
            "race_columns": table_columns(conn, schema.race),
            "uma_race_columns": table_columns(conn, schema.uma_race),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_fixture(args: argparse.Namespace) -> int:
    path = build_fixture(args.out)
    print(json.dumps({"ok": True, "fixture": str(path)}, ensure_ascii=False))
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        schema = detect_schema(conn)
        races = fetch_races_on_date(conn, schema, args.date)
        if args.race_num:
            races = [r for r in races if int(r.get("RaceNum") or 0) == int(args.race_num)]
        if not races:
            print(json.dumps({"error": "no races", "date": args.date}, ensure_ascii=False))
            return 1

        results = []
        for race in races:
            rid = _race_id_from_row(race)
            entries = fetch_entries(conn, schema, rid)
            past_by: dict[str, list] = {}
            for e in entries:
                ketto = str(e.get("KettoNum") or "")
                if not ketto:
                    continue
                past_by[ketto] = fetch_past_runs(conn, schema, ketto, args.date, limit=10)
            # odds lookup from wide table if present
            odds_lookup = {}
            if schema.odds_wide:
                cols = set(table_columns(conn, schema.odds_wide))
                try:
                    rows = conn.execute(f'SELECT * FROM "{schema.odds_wide}"').fetchall()
                    for row in rows:
                        d = dict(row)
                        a, b = d.get("umaban1"), d.get("umaban2")
                        o = d.get("Odds") or d.get("odds")
                        if a and b and o:
                            odds_lookup[(min(int(a), int(b)), max(int(a), int(b)))] = float(o)
                except Exception:
                    odds_lookup = {}

            pred = predict_race(
                race,
                entries,
                past_by,
                race_id=rid,
                odds_lookup=odds_lookup or None,
            )
            results.append(pred.to_dict())

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="keiba_next", description="新予想システム CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    ping_p = sub.add_parser("ping", help="DB存在とテーブル一覧")
    ping_p.add_argument("--db", required=True)
    ping_p.set_defaults(func=cmd_ping)

    insp = sub.add_parser("inspect", help="スキーマ自動検出")
    insp.add_argument("--db", required=True)
    insp.set_defaults(func=cmd_inspect)

    fix = sub.add_parser("fixture", help="開発用ミニDBを生成")
    fix.add_argument("--out", default="next/out/fixture.db")
    fix.set_defaults(func=cmd_fixture)

    pred = sub.add_parser("predict", help="日付のレースを予想")
    pred.add_argument("--db", required=True)
    pred.add_argument("--date", required=True, help="YYYYMMDD")
    pred.add_argument("--race-num", type=int, default=None)
    pred.set_defaults(func=cmd_predict)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
