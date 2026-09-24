"""Playwright smoke test for Streamlit PDF job UI (tab layout)."""

from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ART = Path("/opt/cursor/artifacts")
ART.mkdir(parents=True, exist_ok=True)
PDF = Path("/workspace/samples/sample_invoice.pdf")
BASE = "http://127.0.0.1:8501"


def click_tab(page, name: str) -> None:
    page.get_by_role("tab", name=name).click()
    time.sleep(0.6)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(BASE, wait_until="networkidle")
        page.get_by_text("構造くん").first.wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_tabs_home.png"), full_page=True)

        click_tab(page, "案件")
        page.get_by_label("お客様名や案件名").fill("ui_tabs2")
        page.get_by_role("button", name="案件フォルダを作る").click()
        page.get_by_text(re.compile(r"作りました:\s*20")).first.wait_for(timeout=30000)
        time.sleep(0.8)
        page.screenshot(path=str(ART / "ui_tabs_job.png"), full_page=True)

        click_tab(page, "PDF")
        page.locator('input[type="file"]').set_input_files(str(PDF))
        page.get_by_text(re.compile(r"保存しました:\s*sample_invoice")).first.wait_for(timeout=30000)
        page.get_by_role("button", name="PDFをチェックする").click()
        page.get_by_text("文字を選択できるPDFです", exact=False).first.wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_tabs_pdf.png"), full_page=True)

        click_tab(page, "列設定")
        page.get_by_role("button", name="列設定を保存").click()
        page.get_by_text("次は「抽出」タブへ").first.wait_for(timeout=30000)
        page.screenshot(path=str(ART / "ui_tabs_columns.png"), full_page=True)

        click_tab(page, "抽出")
        page.get_by_role("button", name="抽出する").click()
        page.get_by_text("見つかった表一覧").first.wait_for(timeout=60000)
        page.screenshot(path=str(ART / "ui_tabs_extract.png"), full_page=True)

        click_tab(page, "納品")
        page.get_by_role("button", name="成果物をつくる").click()
        page.get_by_text(re.compile("作成完了")).first.wait_for(timeout=60000)
        page.get_by_role("tab", name=re.compile("data")).first.wait_for(timeout=10000)
        page.screenshot(path=str(ART / "ui_tabs_delivery.png"), full_page=True)

        assert page.get_by_role("button", name="Excelをダウンロード").count() >= 1
        assert page.get_by_role("button", name="CSVをダウンロード").count() >= 1
        print("UI_TABS_SMOKE_OK")
        browser.close()


if __name__ == "__main__":
    main()
