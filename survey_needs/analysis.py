"""アンケート(Google フォーム等の CSV)の集計ロジック。画面(survey_app.py)から独立していてテストしやすい。"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# 列名の自動認識に使うキーワード(質問タイトルにこれらを含める。questionnaire.md 参照)
KEYS = {
    "role": ["職種"],
    "position": ["あなたの立場", "立場"],
    "experience": ["経験年数"],
    "facility": ["施設種別"],
    "authority": ["決裁", "決定権"],
    "intent": ["購入意向"],
    "payer": ["支払う人", "負担しますか"],
    "form": ["提供形態", "希望する形"],
    "free_pain": ["困っていること"],
    "free_wish": ["あったらいい"],
    "chore_pick": ["負担が大きい雑務"],
    "price_band": ["いくらまで払えますか", "いくらまで"],
    "p_too_cheap": ["安すぎて"],
    "p_cheap": ["安い"],
    "p_expensive": ["高い"],
    "p_too_expensive": ["高すぎて"],
}
PRICE_KEYS = ["p_too_cheap", "p_cheap", "p_expensive", "p_too_expensive"]


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """キーワードを含む最初の列を割り当てる。価格4列は「高すぎて」→「高い」の順に、重複を避けて決める。"""
    found: dict[str, str | None] = {}
    used: set[str] = set()
    order = ["p_too_cheap", "p_too_expensive", "p_cheap", "p_expensive"] + \
            [k for k in KEYS if k not in PRICE_KEYS]
    for key in order:
        found[key] = None
        for col in df.columns:
            if col in used or "負担度" in col or "解決意欲" in col:
                continue
            if any(w in col for w in KEYS[key]):
                found[key] = col
                used.add(col)
                break
    return found


def grid_columns(df: pd.DataFrame, keyword: str) -> dict[str, str]:
    """グリッド質問 '…負担度… [行名]' の {行名: 列名}。"""
    out = {}
    for col in df.columns:
        if keyword in col:
            m = re.search(r"\[(.+?)\]\s*$", col)
            out[m.group(1) if m else col] = col
    return out


def to_num(s: pd.Series) -> pd.Series:
    """'1', '3,000円', '5(とても負担)' などから数値を取り出す。"""
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")


def chore_scores(df: pd.DataFrame, burden: dict[str, str], desire: dict[str, str]) -> pd.DataFrame:
    """雑務ごとの 負担度・解決意欲の平均と『需要スコア』。
    需要スコア = 平均負担度 × 平均解決意欲 (1〜25)。上位=負担が大きく、お金を払ってでも解決したい。
    高意欲率 = 解決意欲が4以上の回答者の割合。"""
    rows = []
    for item in burden:
        b = to_num(df[burden[item]])
        d = to_num(df[desire[item]]) if item in desire else pd.Series(dtype=float)
        rows.append({
            "雑務": item, "回答数": int(b.notna().sum()),
            "平均負担度": round(b.mean(), 2),
            "平均解決意欲": round(d.mean(), 2) if len(d) else np.nan,
            "高意欲率(4以上)": round((d >= 4).mean() * 100, 1) if len(d) else np.nan,
            "需要スコア": round(b.mean() * d.mean(), 2) if len(d) else np.nan,
        })
    return pd.DataFrame(rows).sort_values("需要スコア", ascending=False).reset_index(drop=True)


def chore_by_group(df: pd.DataFrame, group_col: str, desire: dict[str, str], min_n: int = 5) -> pd.DataFrame:
    """属性(職種など)別の解決意欲の平均(行=雑務, 列=グループ)。回答数が min_n 未満のグループは除く。"""
    counts = df[group_col].value_counts()
    groups = [g for g, n in counts.items() if n >= min_n]
    res = {}
    for g in groups:
        sub = df[df[group_col] == g]
        res[f"{g}(n={len(sub)})"] = {item: to_num(sub[col]).mean() for item, col in desire.items()}
    return pd.DataFrame(res).round(2)


def van_westendorp(df: pd.DataFrame, cols: dict[str, str | None]) -> dict:
    """Van Westendorp 価格感度分析。PMC(下限)・OPP(最適)・IPP(無差別)・PME(上限)を返す。"""
    if any(cols.get(k) is None for k in PRICE_KEYS):
        return {}
    p = pd.DataFrame({k: to_num(df[cols[k]]) for k in PRICE_KEYS}).dropna()
    # 論理的に矛盾する回答(安すぎる > 安い > 高い > 高すぎる)を除外
    p = p[(p.p_too_cheap <= p.p_cheap) & (p.p_cheap <= p.p_expensive) & (p.p_expensive <= p.p_too_expensive)]
    if len(p) < 5:
        return {"n": len(p)}
    grid = np.linspace(0, float(p.p_too_expensive.max()), 400)
    n = len(p)
    too_cheap = np.array([(p.p_too_cheap >= x).sum() for x in grid]) / n         # 下がる
    cheap = np.array([(p.p_cheap >= x).sum() for x in grid]) / n                 # 下がる
    expensive = np.array([(p.p_expensive <= x).sum() for x in grid]) / n         # 上がる
    too_exp = np.array([(p.p_too_expensive <= x).sum() for x in grid]) / n       # 上がる
    not_cheap, not_exp = 1 - cheap, 1 - expensive

    def cross(a, b):
        diff = a - b
        idx = np.where(np.sign(diff[:-1]) * np.sign(diff[1:]) <= 0)[0]
        return float(grid[idx[0]]) if len(idx) else float("nan")

    return {
        "n": n, "grid": grid,
        "curves": {"安すぎる": too_cheap, "安い": cheap, "高い": expensive, "高すぎる": too_exp},
        "PMC(許容下限)": cross(too_cheap, not_cheap),
        "OPP(最適価格)": cross(too_cheap, too_exp),
        "IPP(無差別価格)": cross(cheap, expensive),
        "PME(許容上限)": cross(too_exp, not_exp),
    }


def counts(s: pd.Series) -> pd.Series:
    """グラフ用の件数集計(列名に「:」等が入ってもグラフが壊れないよう名前を付け替える)。"""
    return s.value_counts().rename("件数").rename_axis("回答")


def intent_summary(df: pd.DataFrame, col: str) -> pd.DataFrame:
    vc = df[col].value_counts(dropna=True).rename_axis("回答")
    return pd.DataFrame({"回答数": vc, "割合(%)": (vc / vc.sum() * 100).round(1)})


def multi_choice_counts(df: pd.DataFrame, col: str, sep: str = ",") -> pd.Series:
    """複数選択(カンマ区切り)の集計。"""
    items = df[col].dropna().astype(str).str.split(sep).explode().str.strip()
    return items[items != ""].value_counts().rename("件数").rename_axis("回答")


def keyword_counts(texts: pd.Series, keywords: list[str]) -> pd.DataFrame:
    """自由記述に指定キーワードが何件含まれるか(部分一致)。"""
    t = texts.dropna().astype(str)
    return pd.DataFrame(
        sorted(((k, int(t.str.contains(re.escape(k)).sum())) for k in keywords if k), key=lambda x: -x[1]),
        columns=["キーワード", "件数"])


def _band_value(label: str) -> float:
    """価格帯ラベルを並べ替え用の数値にする。'払わない'→0, '〜3,000円'→3000, '50,000円超'→50000.5"""
    if "払わない" in label:
        return 0.0
    m = re.search(r"(\d[\d,]*)", label)
    if not m:
        return float("inf")
    v = float(m.group(1).replace(",", ""))
    return v + 0.5 if "超" in label else v


def price_band_counts(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """簡易版の価格質問(選択式)の集計。選択肢は金額の小さい順、累積(その価格以上を許容する割合)も返す。"""
    vc = df[col].value_counts()
    order = sorted(vc.index, key=_band_value)
    out = pd.DataFrame({"回答数": [int(vc[b]) for b in order]}, index=pd.Index(order, name="回答"))
    out["割合(%)"] = (out["回答数"] / out["回答数"].sum() * 100).round(1)
    out["この金額以上を許容(%)"] = (out["割合(%)"][::-1].cumsum()[::-1]).round(1)
    return out


def pick_by_group(df: pd.DataFrame, pick_col: str, group_col: str, min_n: int = 5, sep: str = ",") -> pd.DataFrame:
    """複数選択の雑務 × 職種 の選択率(%)。"""
    rows = {}
    for g, sub in df.groupby(group_col):
        if len(sub) < min_n:
            continue
        c = multi_choice_counts(sub, pick_col, sep)
        rows[f"{g}(n={len(sub)})"] = (c / len(sub) * 100).round(1)
    return pd.DataFrame(rows).fillna(0)
