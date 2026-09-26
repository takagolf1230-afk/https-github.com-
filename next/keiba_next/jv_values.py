"""JV-Data / EveryDB2 の文字数値を実数に戻す。オッズは印の特徴に使わない。"""

from __future__ import annotations

# 馬毎レース SE のデータ区分。月曜確定が最も新しい成績。
SE_KUBUN_RANK = {
    "7": 70,
    "6": 60,
    "5": 50,
    "4": 40,
    "3": 30,
    "2": 20,
    "1": 10,
    "A": 8,
    "B": 8,
}
SE_RESULT_KUBUN = {"7", "6", "5", "4", "3", "A", "B"}
# 払戻 HR。2 が月曜確定、1 が速報。
HR_KUBUN_RANK = {"2": 20, "1": 10}

# 小文字の列名を EveryDB2 の名前へ寄せる。
CANONICAL = {
    "year": "Year",
    "monthday": "MonthDay",
    "jyocd": "JyoCD",
    "kaiji": "Kaiji",
    "nichiji": "Nichiji",
    "racenum": "RaceNum",
    "kyori": "Kyori",
    "distance": "Kyori",
    "trackcd": "TrackCD",
    "track": "TrackCD",
    "syussotosu": "SyussoTosu",
    "datakubun": "DataKubun",
    "kettonum": "KettoNum",
    "umaban": "Umaban",
    "bamei": "Bamei",
    "kakuteijyuni": "KakuteiJyuni",
    "harontimel3": "HaronTimeL3",
    "agari": "HaronTimeL3",
    "timel3": "HaronTimeL3",
    "bataiju": "BaTaiju",
    "weight": "BaTaiju",
    "zogensa": "ZogenSa",
    "zogen_sa": "ZogenSa",
    "zogenfugo": "ZogenFugo",
    "futan": "Futan",
    "burden": "Futan",
    "kisyucode": "KisyuCode",
    "kisyu": "KisyuCode",
    "jyuni1c": "Jyuni1c",
    "jyuni2c": "Jyuni2c",
    "jyuni3c": "Jyuni3c",
    "jyuni4c": "Jyuni4c",
    "ijyocd": "IJyoCD",
    "odds": "Odds",
    "paytansyoumaban1": "PayTansyoUmaban1",
    "paytansyoumaban2": "PayTansyoUmaban2",
    "paytansyoumaban3": "PayTansyoUmaban3",
    "paytansyopay1": "PayTansyoPay1",
    "fuseirituflag1": "FuseirituFlag1",
}


def canonical_row(row: dict) -> dict:
    out: dict = {}
    for key, value in row.items():
        canon = CANONICAL.get(str(key).lower(), key)
        if canon in out and out[canon] not in (None, ""):
            continue
        out[canon] = value
    return out


def norm_code(value, width: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.isdigit():
        return text.zfill(width)
    return text


def date_key(year, monthday) -> str:
    return f"{int(str(year).strip()):04d}{int(str(monthday).strip()):04d}"


def clean_code(value) -> str:
    text = str(value or "").strip()
    if not text or set(text) <= {"0"}:
        return ""
    return text


def se_kubun_rank(value) -> int:
    return SE_KUBUN_RANK.get(str(value or "").strip().upper(), 0)


def hr_kubun_rank(value) -> int:
    return HR_KUBUN_RANK.get(str(value or "").strip(), 0)


def finish_place(value) -> int | None:
    if value in (None, "", "00", "0"):
        return None
    try:
        place = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if 1 <= place <= 18:
        return place
    return None


def is_scratched(row: dict) -> bool:
    """取消・除外・中止。失格と降着は着順があるので残す。"""
    code = str(row.get("IJyoCD") or "").strip()
    if code in {"1", "2", "3"}:
        return True
    umaban = norm_code(row.get("Umaban"), 2)
    return umaban in {"", "00"}


def _raw_number(value) -> float | None:
    if value in (None, "", "0", "00", "000", "0000"):
        return None
    text = str(value).strip()
    if not text or set(text) <= {"0"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def agari_seconds(row: dict) -> float:
    """後3ハロン。348 → 34.8秒。999 と 000 は欠損。"""
    raw = None
    for key in ("HaronTimeL3", "Agari", "TimeL3"):
        if key in row:
            raw = _raw_number(row.get(key))
            if raw is not None:
                break
    if raw is None or raw >= 999:
        return 0.0
    if raw > 100:
        raw = raw / 10.0
    if raw >= 99.9:
        return 0.0
    return raw


def body_weight_kg(row: dict) -> float:
    raw = _raw_number(row.get("BaTaiju"))
    if raw is None or raw >= 700:
        return 0.0
    return raw


def weight_delta_kg(row: dict) -> float:
    """ZogenSa は絶対値、ZogenFugo が符号。"""
    raw = _raw_number(row.get("ZogenSa"))
    if raw is None:
        return 0.0
    sign = str(row.get("ZogenFugo") or "").strip()
    if sign in {"-", "−"}:
        return -abs(raw)
    return raw


def futan_kg(row: dict) -> float:
    """斤量。560 → 56.0kg。既に 56.0 ならそのまま。"""
    raw = _raw_number(row.get("Futan"))
    if raw is None:
        return 0.0
    if raw > 70:
        raw = raw / 10.0
    if raw < 40 or raw > 70:
        return 0.0
    return raw


def corner_place(value) -> float | None:
    place = _raw_number(value)
    if place is None or place < 1 or place > 28:
        return None
    return place


def corner_average(row: dict) -> float:
    places = [corner_place(row.get(key)) for key in ("Jyuni1c", "Jyuni2c", "Jyuni3c", "Jyuni4c")]
    places = [p for p in places if p is not None]
    if not places:
        return 0.0
    return sum(places) / len(places)


def tan_odds(row: dict) -> float | None:
    """確定単勝オッズ。4桁の 0.1 倍。印の特徴には入れない。"""
    if row.get("TanOdds") not in (None, ""):
        try:
            value = float(row["TanOdds"])
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None
    raw = row.get("Odds")
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    if not text or set(text) <= {"0"} or text in {"9999", "0000"}:
        return None
    try:
        if "." in text:
            value = float(text)
        else:
            value = int(text) / 10.0
    except ValueError:
        return None
    if value <= 0 or value >= 999.9:
        return None
    return value


def tansyo_umabans(row: dict) -> list[int]:
    found: list[int] = []
    for index in (1, 2, 3):
        place = finish_place(row.get(f"PayTansyoUmaban{index}"))
        if place is not None:
            found.append(place)
    return found
