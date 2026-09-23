"""CLI: new / check / extract / deliver — beginner PDF job pipeline."""

from __future__ import annotations

import argparse
import shutil
import sys
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


def _slug(name: str) -> str:
    import re

    cleaned = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    return cleaned.strip("_") or "job"


def cmd_new(args: argparse.Namespace) -> int:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    folder = JOBS_DIR / f"{date.today().strftime('%Y%m%d')}_{_slug(args.name)}"
    if folder.exists():
        print(f"すでにあります: {folder}")
        return 1
    (folder / "01_input").mkdir(parents=True)
    (folder / "02_work").mkdir()
    (folder / "03_delivery").mkdir()
    shutil.copy(TEMPLATES / "intake.md", folder / "00_intake.md")
    shutil.copy(TEMPLATES / "columns.example.yaml", folder / "columns.yaml")
    readme = folder / "README_作業手順.txt"
    readme.write_text(
        "\n".join(
            [
                "【このフォルダの使い方】",
                "1. お客様のPDFを 01_input/ に置く",
                "2. 00_intake.md を埋める（欲しい列・ページ）",
                "3. columns.yaml の name / source / type を依頼どおりに直す",
                "4. 文字が選べるか確認:",
                f"   python -m tools.pdf_job check --job {folder.name}",
                "5. 表を抜き出す:",
                f"   python -m tools.pdf_job extract --job {folder.name}",
                "6. 02_work/raw_preview.xlsx を見て列名を合わせる",
                "7. 納品ファイルを作る:",
                f"   python -m tools.pdf_job deliver --job {folder.name}",
                "8. 03_delivery/ の xlsx と csv を目視して納品",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"案件フォルダを作りました: {folder}")
    print("次: お客様のPDFを 01_input/ に入れてください。")
    return 0


def _resolve_job(name: str) -> Path:
    path = Path(name)
    if not path.is_absolute():
        candidate = JOBS_DIR / name
        if candidate.exists():
            path = candidate
    if not path.exists():
        raise FileNotFoundError(f"案件フォルダが見つかりません: {name}")
    return path.resolve()


def _find_pdf(job: Path) -> Path:
    input_dir = job / "01_input"
    pdfs = sorted(input_dir.glob("*.pdf")) + sorted(input_dir.glob("*.PDF"))
    if not pdfs:
        raise FileNotFoundError(f"PDFがありません: {input_dir}")
    if len(pdfs) > 1:
        print(f"PDFが複数あります。先頭を使います: {pdfs[0].name}")
    return pdfs[0]


def cmd_check(args: argparse.Namespace) -> int:
    job = _resolve_job(args.job)
    pdf = _find_pdf(job)
    pages = page_count(pdf)
    selectable = is_text_selectable(pdf)
    print(f"PDF: {pdf.name}")
    print(f"ページ数: {pages}")
    if selectable:
        print("判定: 文字を選択できるPDFです（基本料金の対象になりやすい）")
    else:
        print("判定: 文字を選べません。スキャン／画像PDFの可能性が高いです。")
        print("      → オプション +2,000円、またはお断り／要確認を先に伝えてください。")
    if pages > 5:
        print(f"注意: {pages}ページです。基本は5ページまで。追加ページオプションを提案してください。")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    job = _resolve_job(args.job)
    pdf = _find_pdf(job)
    schema_path = job / "columns.yaml"
    pages = None
    if schema_path.exists():
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
        pages = schema.get("pages")

    tables = extract_tables(pdf, pages=pages)
    work = job / "02_work"
    work.mkdir(exist_ok=True)

    preview_path = work / "raw_preview.xlsx"
    with pd.ExcelWriter(preview_path, engine="openpyxl") as writer:
        index_rows = []
        wrote_any = False
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

    print(f"抽出プレビュー: {preview_path}")
    print("Excelで index シートと各表を見て、columns.yaml の source を合わせてください。")
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    job = _resolve_job(args.job)
    pdf = _find_pdf(job)
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
            log_rows.append(
                {
                    "page": page,
                    "table": idx,
                    "status": "skipped",
                    "detail": note or "空の表",
                }
            )
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
        print("データ行を作れませんでした。extract のプレビューと columns.yaml を見直してください。")
        return 1

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
        stem=args.stem or "成果物",
    )
    print(f"納品Excel: {out['xlsx']}")
    print(f"納品CSV : {out['csv']}")
    print(f"データ行数: {len(data_df)} / 要確認: {0 if review_df.empty else len(review_df)}")
    print("必ず data の先頭・末尾と金額合計を元PDFと目視で突合してから送ってください。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.pdf_job",
        description="ココナラ受注用: PDFの表を依頼列のExcel/CSVに整える道具",
    )
    sub = p.add_subparsers(dest="command", required=True)

    n = sub.add_parser("new", help="案件フォルダを作る")
    n.add_argument("--name", required=True, help="お客様名や案件名")
    n.set_defaults(func=cmd_new)

    c = sub.add_parser("check", help="文字選択できるPDFか・ページ数を確認")
    c.add_argument("--job", required=True, help="jobs/ 配下のフォルダ名")
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("extract", help="表を抜き出してプレビューExcelを作る")
    e.add_argument("--job", required=True)
    e.set_defaults(func=cmd_extract)

    d = sub.add_parser("deliver", help="依頼列に揃えて納品xlsx/csvを作る")
    d.add_argument("--job", required=True)
    d.add_argument("--stem", default="成果物", help="出力ファイル名（拡張子なし）")
    d.set_defaults(func=cmd_deliver)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - beginner-facing CLI
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
