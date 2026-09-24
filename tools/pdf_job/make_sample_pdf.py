"""Generate a tiny sample PDF with a Japanese table for local practice."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _register_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            # TTC: subfontIndex 0 usually works for wqy-microhei
            try:
                pdfmetrics.registerFont(TTFont("JobSans", path, subfontIndex=0))
            except Exception:
                pdfmetrics.registerFont(TTFont("JobSans", path))
            return "JobSans"
    return "Helvetica"


def build_sample_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    font = _register_font()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("JaTitle", parent=styles["Title"], fontName=font, fontSize=16)
    data = [
        ["日付", "商品名", "数量", "金額"],
        ["2026/01/01", "商品A", "10", "12,000"],
        ["2026/01/02", "商品B", "3", "4,500"],
        ["2026年1月3日", "商品Ｃ", "２", "８０００"],
        ["2026/01/02", "商品B", "3", "4,500"],
    ]
    table = Table(data, colWidths=[35 * mm, 50 * mm, 25 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story = [
        Paragraph("練習用サンプル請求明細", title_style),
        Spacer(1, 8 * mm),
        table,
    ]
    doc.build(story)
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "samples" / "sample_invoice.pdf"
    print(build_sample_pdf(out))
