"""Extract tables from text-selectable PDFs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd


def _row_is_empty(row: list[Any]) -> bool:
    return all(cell is None or str(cell).strip() == "" for cell in row)


def table_to_dataframe(table: list[list[Any]]) -> pd.DataFrame:
    rows = [r for r in table if not _row_is_empty(r)]
    if not rows:
        return pd.DataFrame()
    width = max(len(r) for r in rows)
    normalized = [list(r) + [None] * (width - len(r)) for r in rows]
    header = [str(c).strip() if c is not None else f"col_{i+1}" for i, c in enumerate(normalized[0])]
    # Deduplicate header names
    seen: dict[str, int] = {}
    uniq: list[str] = []
    for name in header:
        key = name or "col"
        if key in seen:
            seen[key] += 1
            uniq.append(f"{key}_{seen[key]}")
        else:
            seen[key] = 0
            uniq.append(key)
    body = normalized[1:] if len(normalized) > 1 else []
    return pd.DataFrame(body, columns=uniq)


def extract_tables(
    pdf_path: Path,
    pages: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Return list of {page, table_index, dataframe} (1-indexed pages)."""
    results: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        page_numbers = pages or list(range(1, len(pdf.pages) + 1))
        for page_no in page_numbers:
            if page_no < 1 or page_no > len(pdf.pages):
                continue
            page = pdf.pages[page_no - 1]
            tables = page.extract_tables() or []
            if not tables:
                # Fallback: try text lines as single-column preview cue
                text = (page.extract_text() or "").strip()
                results.append(
                    {
                        "page": page_no,
                        "table_index": 0,
                        "dataframe": pd.DataFrame(),
                        "note": "表を検出できませんでした" + (f"（文字はあります: {text[:80]}…）" if text else "（スキャンの可能性）"),
                    }
                )
                continue
            for idx, table in enumerate(tables, start=1):
                df = table_to_dataframe(table)
                results.append(
                    {
                        "page": page_no,
                        "table_index": idx,
                        "dataframe": df,
                        "note": "" if not df.empty else "空の表",
                    }
                )
    return results


def is_text_selectable(pdf_path: Path, sample_pages: int = 2) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:sample_pages]:
            if (page.extract_text() or "").strip():
                return True
    return False


def page_count(pdf_path: Path) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)
