"""End-to-end demo: PDF table -> structured data -> Excel/CSV/SQLite.

Mirrors the core "structure a messy PDF table into analysis-ready data" flow:
generate a sample invoice-style PDF, extract its table, normalize types,
export to xlsx and csv, and load into SQLite for an aggregation query.

Run: python3 examples/pdf_to_table.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Raw rows as they might appear in a source PDF: mixed date formats,
# currency symbols and thousands separators that break naive conversion.
RAW_ROWS = [
    ["Date", "Product", "Quantity", "Amount"],
    ["2026/01/01", "Widget A", "10", "$12,000"],
    ["2026-01-03", "Widget B", "5", "8,500"],
    ["Jan 7, 2026", "Widget A", "3", "$3,600"],
    ["2026/01/09", "Widget C", "12", "24,000"],
    ["2026-01-15", "Widget B", "7", "$11,900"],
]


def build_sample_pdf(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    table = Table(RAW_ROWS)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    doc.build([table])


def extract_table(path: Path) -> pd.DataFrame:
    with pdfplumber.open(str(path)) as pdf:
        rows = pdf.pages[0].extract_table()
    header, *data = rows
    return pd.DataFrame(data, columns=header)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
    out["product"] = df["Product"].str.strip()
    out["quantity"] = df["Quantity"].astype(int)
    out["amount"] = df["Amount"].str.replace(r"[$,\s]", "", regex=True).astype(int)
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT_DIR / "sample_invoice.pdf"
    xlsx_path = OUTPUT_DIR / "structured.xlsx"
    csv_path = OUTPUT_DIR / "structured.csv"
    db_path = OUTPUT_DIR / "structured.db"

    build_sample_pdf(pdf_path)
    print(f"[1/5] Generated sample PDF: {pdf_path}")

    raw = extract_table(pdf_path)
    print(f"[2/5] Extracted table from PDF ({len(raw)} rows)")

    df = normalize(raw)
    print("[3/5] Normalized types (mixed date formats / currency strings):")
    print(df.to_string(index=False))

    df.to_excel(xlsx_path, index=False)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"[4/5] Wrote {xlsx_path.name} and {csv_path.name}")

    with sqlite3.connect(db_path) as conn:
        df.to_sql("sales", conn, if_exists="replace", index=False)
        summary = pd.read_sql_query(
            "SELECT product, SUM(quantity) AS qty, SUM(amount) AS total "
            "FROM sales GROUP BY product ORDER BY total DESC",
            conn,
        )
    print("[5/5] SQLite aggregation (SUM by product):")
    print(summary.to_string(index=False))

    verify = pd.read_excel(xlsx_path)
    assert len(verify) == len(df), "xlsx round-trip row count mismatch"
    assert int(df["amount"].sum()) == 60000, "unexpected amount total"
    print("\nOK: round-trip verified, totals reconcile (amount sum = 60000).")


if __name__ == "__main__":
    main()
