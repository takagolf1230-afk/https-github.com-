"""Playwright smoke test for Streamlit PDF job UI."""

from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ART = Path("/opt/cursor/artifacts")
ART.mkdir(parents=True, exist_ok=True)
PDF = Path("/workspace/samples/sample_invoice.pdf")
BASE = "http://127.0.0.1:8501"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(BASE, wait_until="networkidle")
        page.get_by_text("① 案件を用意する").wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_step1_jobs.png"), full_page=True)

        # Create job
        page.get_by_label("お客様名や案件名").fill("ui_play")
        page.get_by_role("button", name="案件フォルダを作る").click()
        page.get_by_text("② PDFを入れて確認する").wait_for(timeout=30000)
        time.sleep(1)
        page.screenshot(path=str(ART / "ui_step2_pdf.png"), full_page=True)

        # Upload PDF
        page.locator('input[type="file"]').set_input_files(str(PDF))
        page.get_by_text("保存しました").wait_for(timeout=30000)
        page.get_by_role("button", name="PDFをチェックする").click()
        page.get_by_text(re.compile("文字を選択できる")).wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_step2_checked.png"), full_page=True)
        page.get_by_role("button", name=re.compile("次へ：列の設定")).click()

        page.get_by_text("③ 依頼された列を設定する").wait_for(timeout=30000)
        page.get_by_role("button", name="列設定を保存").click()
        page.get_by_text("保存しました").wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_step3_columns.png"), full_page=True)
        page.get_by_role("button", name=re.compile("次へ：抽出プレビュー")).click()

        page.get_by_text("④ 表を抜き出して確認する").wait_for(timeout=30000)
        page.get_by_role("button", name="抽出する").click()
        page.get_by_text("見つかった表一覧").wait_for(timeout=60000)
        page.screenshot(path=str(ART / "ui_step4_extract.png"), full_page=True)
        page.get_by_role("button", name=re.compile("次へ：納品作成")).click()

        page.get_by_text("⑤ 納品ファイルを作る").wait_for(timeout=30000)
        page.get_by_role("button", name="成果物をつくる").click()
        page.get_by_text(re.compile("作成完了")).wait_for(timeout=60000)
        page.get_by_text("data（納品本体）").wait_for(timeout=10000)
        page.screenshot(path=str(ART / "ui_step5_delivery.png"), full_page=True)

        # Sanity: download buttons present
        assert page.get_by_role("button", name="Excelをダウンロード").count() >= 1
        assert page.get_by_role("button", name="CSVをダウンロード").count() >= 1
        print("UI_SMOKE_OK")
        browser.close()


if __name__ == "__main__":
    main()
