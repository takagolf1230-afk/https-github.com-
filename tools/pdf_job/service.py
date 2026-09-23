"""Shared job operations used by CLI and Streamlit UI."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .deliver import drop_exact_duplicates, load_schema, map_dataframe, write_delivery
from .extract import extract_tables, is_text_selectable, page_count

ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = ROOT / "jobs"
TEMPLATES = Path(__file__).resolve().parent / "templates"


def slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    return cleaned.strip("_") or "job"


def resolve_job(name: str | Path) -> Path:
    path = Path(name)
    if not path.is_absolute():
        candidate = JOBS_DIR / str(name)
        if candidate.exists():
            path = candidate
    if not path.exists():
        raise FileNotFoundError(f"案件フォルダが見つかりません: {name}")
    return path.resolve()


def list_jobs() -> list[Path]:
    if not JOBS_DIR.exists():
        return []
    return sorted([p for p in JOBS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")], reverse=True)


def find_pdf(job: Path) -> Path:
    input_dir = job / "01_input"
    pdfs = sorted(input_dir.glob("*.pdf")) + sorted(input_dir.glob("*.PDF"))
    if not pdfs:
        raise FileNotFoundError(f"PDFがありません: {input_dir}")
    return pdfs[0]


def create_job(name: str) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    folder = JOBS_DIR / f"{date.today().strftime('%Y%m%d')}_{slug(name)}"
    if folder.exists():
        raise FileExistsError(f"すでにあります: {folder}")
    (folder / "01_input").mkdir(parents=True)
    (folder / "02_work").mkdir()
    (folder / "03_delivery").mkdir()
    shutil.copy(TEMPLATES / "intake.md", folder / "00_intake.md")
    shutil.copy(TEMPLATES / "columns.example.yaml", folder / "columns.yaml")
    (folder / "README_作業手順.txt").write_text(
        "画面版: python -m streamlit run tools/pdf_job/app.py\n"
        "コマンド版は docs/beginner_runbook.md を参照\n",
        encoding="utf-8",
    )
    return folder


def save_uploaded_pdf(job: Path, filename: str, data: bytes) -> Path:
    target = job / "01_input" / Path(filename).name
    if not target.suffix.lower() == ".pdf":
        raise ValueError("PDFファイルのみ保存できます")
    # keep single working PDF for beginners
    for old in (job / "01_input").glob("*.pdf"):
        old.unlink()
    for old in (job / "01_input").glob("*.PDF"):
        old.unlink()
    target.write_bytes(data)
    return target


def load_columns_yaml(job: Path) -> dict[str, Any]:
    path = job / "columns.yaml"
    if not path.exists():
        return {"pages": None, "columns": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"pages": None, "columns": []}


def save_columns_yaml(job: Path, data: dict[str, Any]) -> Path:
    path = job / "columns.yaml"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def check_job(job: Path) -> dict[str, Any]:
    pdf = find_pdf(job)
    pages = page_count(pdf)
    selectable = is_text_selectable(pdf)
    messages: list[str] = []
    if selectable:
        messages.append("文字を選択できるPDFです（基本料金の対象になりやすい）")
    else:
        messages.append("文字を選べません。スキャン／画像PDFの可能性が高いです。")
        messages.append("オプション +2,000円、またはお断り／要確認を先に伝えてください。")
    if pages > 5:
        messages.append(f"{pages}ページです。基本は5ページまで。追加ページオプションを提案してください。")
    return {
        "pdf_name": pdf.name,
        "pages": pages,
        "selectable": selectable,
        "messages": messages,
    }


def extract_job(job: Path) -> dict[str, Any]:
    pdf = find_pdf(job)
    schema = load_columns_yaml(job)
    pages = schema.get("pages")
    tables = extract_tables(pdf, pages=pages)
    work = job / "02_work"
    work.mkdir(exist_ok=True)
    preview_path = work / "raw_preview.xlsx"
    index_rows: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    wrote_any = False
    with pd.ExcelWriter(preview_path, engine="openpyxl") as writer:
        for item in tables:
            page = item["page"]
            idx = item["table_index"]
            df: pd.DataFrame = item["dataframe"]
            note = item.get("note") or ""
            sheet = f"p{page}_t{idx}"[:31]
            index_rows.append(
                {
                    "sheet": sheet,
                    "page": page,
                    "table_index": idx,
                    "rows": len(df),
                    "cols": len(df.columns),
                    "columns": ", ".join(map(str, df.columns)),
                    "note": note,
                }
            )
            previews.append({"sheet": sheet, "page": page, "table_index": idx, "dataframe": df, "note": note})
            if df.empty:
                pd.DataFrame([{"note": note or "空"}]).to_excel(writer, sheet_name=sheet, index=False)
            else:
                df.to_excel(writer, sheet_name=sheet, index=False)
                wrote_any = True
        pd.DataFrame(index_rows).to_excel(writer, sheet_name="index", index=False)
        if not wrote_any:
            pd.DataFrame([{"memo": "表が取れませんでした。スキャンの可能性を確認してください。"}]).to_excel(
                writer, sheet_name="help", index=False
            )
    return {
        "preview_path": preview_path,
        "index": pd.DataFrame(index_rows),
        "tables": previews,
        "found_any": wrote_any,
    }


def deliver_job(job: Path, stem: str = "成果物") -> dict[str, Any]:
    pdf = find_pdf(job)
    schema = load_schema(job / "columns.yaml")
    pages = schema.get("pages")
    tables = extract_tables(pdf, pages=pages)

    data_parts: list[pd.DataFrame] = []
    review_parts: list[pd.DataFrame] = []
    log_rows: list[dict[str, Any]] = []

    for item in tables:
        df = item["dataframe"]
        page = item["page"]
        idx = item["table_index"]
        note = item.get("note") or ""
        if df.empty:
            log_rows.append({"page": page, "table": idx, "status": "skipped", "detail": note or "空の表"})
            if note:
                review_parts.append(
                    pd.DataFrame(
                        [
                            {
                                "page": page,
                                "table": idx,
                                "row": "",
                                "column": "",
                                "raw": "",
                                "issue": note,
                            }
                        ]
                    )
                )
            continue
        mapped, review = map_dataframe(df, schema, page, idx)
        data_parts.append(mapped)
        if not review.empty:
            review_parts.append(review)
        log_rows.append(
            {
                "page": page,
                "table": idx,
                "status": "ok",
                "detail": f"{len(mapped)}行 / 列={list(mapped.columns)}",
            }
        )

    if not data_parts:
        raise ValueError("データ行を作れませんでした。プレビューと列設定を見直してください。")

    data_df = pd.concat(data_parts, ignore_index=True)
    value_cols = [c["name"] for c in schema["columns"]]
    data_df, dropped = drop_exact_duplicates(data_df, value_cols)
    if dropped:
        log_rows.append({"page": "", "table": "", "status": "dedupe", "detail": f"完全一致の重複を{dropped}行削除"})

    review_df = pd.concat(review_parts, ignore_index=True) if review_parts else pd.DataFrame()
    out = write_delivery(
        data_df=data_df,
        review_df=review_df,
        log_rows=log_rows,
        out_dir=job / "03_delivery",
        stem=stem,
    )
    return {
        "xlsx": out["xlsx"],
        "csv": out["csv"],
        "data": data_df,
        "review": review_df,
        "log": pd.DataFrame(log_rows),
        "rows": len(data_df),
        "review_rows": 0 if review_df.empty else len(review_df),
        "dropped": dropped,
    }
