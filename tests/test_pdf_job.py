"""Lightweight checks for beginner PDF job toolkit."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pdf_job.normalize import parse_date, parse_number, clean_text
from tools.pdf_job.make_sample_pdf import build_sample_pdf
from tools.pdf_job.extract import extract_tables, is_text_selectable
from tools.pdf_job.deliver import map_dataframe, drop_exact_duplicates


def test_normalize() -> None:
    assert clean_text(" ＡＢ　") == "AB"
    assert parse_number("１２,０００円")[0] == 12000
    assert parse_date("2026年1月3日")[0] == "2026-01-03"


def test_sample_pipeline() -> None:
    pdf = ROOT / "samples" / "sample_invoice.pdf"
    build_sample_pdf(pdf)
    assert is_text_selectable(pdf)
    tables = extract_tables(pdf, pages=[1])
    assert tables and not tables[0]["dataframe"].empty
    schema = {
        "columns": [
            {"name": "日付", "source": ["日付"], "type": "date"},
            {"name": "品名", "source": ["商品名"], "type": "text"},
            {"name": "数量", "source": ["数量"], "type": "number"},
            {"name": "金額", "source": ["金額"], "type": "number"},
        ]
    }
    mapped, review = map_dataframe(tables[0]["dataframe"], schema, 1, 1)
    mapped, dropped = drop_exact_duplicates(mapped, ["日付", "品名", "数量", "金額"])
    assert len(mapped) == 3
    assert dropped == 1
    assert review.empty
    assert int(mapped.iloc[2]["数量"]) == 2
    assert int(mapped.iloc[2]["金額"]) == 8000


if __name__ == "__main__":
    test_normalize()
    test_sample_pipeline()
    print("ALL_OK")
