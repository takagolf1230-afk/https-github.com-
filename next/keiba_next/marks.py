"""印付け（◎○▲△☆）。"""

from __future__ import annotations

from typing import Any


MARKS_ORDER = ("◎", "○", "▲", "△", "☆", "×")


def assign_marks(scored: list[dict], max_delta: int = 3) -> list[dict[str, Any]]:
    """win_score 順を主に、△は place、☆は dark。"""
    rows = [dict(r) for r in scored]
    for r in rows:
        r["mark"] = "×"

    if not rows:
        return rows

    rows[0]["mark"] = "◎"
    if len(rows) > 1:
        rows[1]["mark"] = "○"
    if len(rows) > 2:
        rows[2]["mark"] = "▲"

    # △: place_score 上位で未印
    by_place = sorted(rows, key=lambda r: (-float(r.get("place_score") or 0), 0))
    delta_n = 0
    for r in by_place:
        if r["mark"] != "×":
            continue
        if delta_n >= max_delta:
            break
        if float(r.get("place_score") or 0) > 0:
            r["mark"] = "△"
            delta_n += 1

    # ☆: dark が高く、まだ × の1頭
    by_dark = sorted(rows, key=lambda r: (-float(r.get("dark_score") or 0), 0))
    for r in by_dark:
        if r["mark"] == "×" and float(r.get("dark_score") or 0) >= 8:
            r["mark"] = "☆"
            break

    # keep win_score order for output
    rows.sort(key=lambda r: (-float(r.get("win_score") or 0), r.get("Umaban") or 0))
    return rows


def horses_by_mark(marked: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {m: [] for m in MARKS_ORDER}
    for r in marked:
        out.setdefault(r.get("mark", "×"), []).append(r)
    return out
