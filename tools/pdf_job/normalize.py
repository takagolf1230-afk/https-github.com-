"""Text / type normalization helpers for beginner PDF jobs."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd

_FW_NUM = str.maketrans("０１２３４５６７８９．，－ー", "0123456789.,--")
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%Y-%m",
    "%Y/%m",
    "%Y年%m月",
)


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def parse_number(value: Any) -> tuple[Any, str | None]:
    raw = clean_text(value)
    if raw == "":
        return None, None
    candidate = raw.translate(_FW_NUM)
    candidate = candidate.replace(",", "").replace("¥", "").replace("円", "")
    candidate = candidate.replace("%", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", candidate):
        if "." in candidate:
            return float(candidate), None
        return int(candidate), None
    return raw, f"数値に変換できず原文を残しました: {raw}"


def parse_date(value: Any) -> tuple[Any, str | None]:
    raw = clean_text(value)
    if raw == "":
        return None, None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            if "%d" in fmt:
                return dt.date().isoformat(), None
            return dt.strftime("%Y-%m"), None
        except ValueError:
            continue
    # 2026年1月1日 / 2026年01月01日 loosely
    m = re.match(r"^(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?$", raw)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d).date().isoformat(), None
        except ValueError:
            pass
    return raw, f"日付に変換できず原文を残しました: {raw}"


def normalize_cell(value: Any, col_type: str) -> tuple[Any, str | None]:
    col_type = (col_type or "text").lower()
    if col_type in {"number", "int", "float", "金额", "金額"}:
        return parse_number(value)
    if col_type in {"date", "datetime"}:
        return parse_date(value)
    return clean_text(value), None
