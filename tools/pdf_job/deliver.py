"""Map extracted tables into requested columns and write delivery files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .normalize import clean_text, normalize_cell


def load_schema(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "columns" not in data or not data["columns"]:
        raise ValueError(f"columns.yaml に columns がありません: {path}")
    return data


def _match_source_column(df: pd.DataFrame, sources: list[str]) -> str | None:
    cols = list(df.columns)
    lowered = {clean_text(c).lower(): c for c in cols}
    for src in sources:
        key = clean_text(src).lower()
        if key in lowered:
            return lowered[key]
    # partial contains
    for src in sources:
        key = clean_text(src).lower()
        for c in cols:
            if key and key in clean_text(c).lower():
                return c
    return None


def map_dataframe(df: pd.DataFrame, schema: dict[str, Any], page: int, table_index: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = schema["columns"]
    mapped_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    source_map: dict[str, str | None] = {}
    for col in columns:
        name = col["name"]
        sources = col.get("source") or [name]
        if isinstance(sources, str):
            sources = [sources]
        source_map[name] = _match_source_column(df, sources)

    for row_i, row in df.iterrows():
        out: dict[str, Any] = {
            "_source_page": page,
            "_source_table": table_index,
            "_source_row": int(row_i) + 1,
        }
        for col in columns:
            name = col["name"]
            col_type = col.get("type", "text")
            src = source_map[name]
            raw = row[src] if src is not None else None
            value, issue = normalize_cell(raw, col_type)
            out[name] = value
            if src is None:
                review_rows.append(
                    {
                        "page": page,
                        "table": table_index,
                        "row": int(row_i) + 1,
                        "column": name,
                        "raw": "",
                        "issue": f"元表に対応列がありません（候補: {col.get('source', [name])}）",
                    }
                )
            elif issue:
                review_rows.append(
                    {
                        "page": page,
                        "table": table_index,
                        "row": int(row_i) + 1,
                        "column": name,
                        "raw": clean_text(raw),
                        "issue": issue,
                    }
                )
        mapped_rows.append(out)

    data_cols = ["_source_page", "_source_table", "_source_row"] + [c["name"] for c in columns]
    data_df = pd.DataFrame(mapped_rows, columns=data_cols) if mapped_rows else pd.DataFrame(columns=data_cols)
    review_df = pd.DataFrame(review_rows)
    return data_df, review_df


def drop_exact_duplicates(data_df: pd.DataFrame, value_cols: list[str]) -> tuple[pd.DataFrame, int]:
    if data_df.empty:
        return data_df, 0
    before = len(data_df)
    deduped = data_df.drop_duplicates(subset=value_cols, keep="first")
    return deduped.reset_index(drop=True), before - len(deduped)


def write_delivery(
    *,
    data_df: pd.DataFrame,
    review_df: pd.DataFrame,
    log_rows: list[dict[str, Any]],
    out_dir: Path,
    stem: str = "成果物",
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / f"{stem}.xlsx"
    csv_path = out_dir / f"{stem}.csv"
    log_df = pd.DataFrame(log_rows)

    # Delivery sheet without internal helper cols optionally kept for traceability
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        data_df.to_excel(writer, sheet_name="data", index=False)
        if review_df is None or review_df.empty:
            pd.DataFrame(
                [{"memo": "要確認はありません。重要数値は元PDFと抜粋突合してください。"}]
            ).to_excel(writer, sheet_name="review", index=False)
        else:
            review_df.to_excel(writer, sheet_name="review", index=False)
        log_df.to_excel(writer, sheet_name="log", index=False)

    # CSV is data only, without helper columns if present
    export_cols = [c for c in data_df.columns if not str(c).startswith("_")]
    data_df[export_cols].to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {"xlsx": xlsx_path, "csv": csv_path}
