# Coconala PDF→Excel 出品キット + 素人向け作業ソフト

デスクトップの調査結果と、受注後に使う簡単な道具をまとめたリポジトリです。

## まず読むもの（素人向け）

| ファイル | 内容 |
|---|---|
| [`docs/beginner_runbook.md`](docs/beginner_runbook.md) | **受注したらこの順で押すだけ** |
| [`docs/coconala_pdf_excel_listing.md`](docs/coconala_pdf_excel_listing.md) | ココナラ貼り付け用の出品原稿 |
| [`docs/coconala_market_analysis.md`](docs/coconala_market_analysis.md) | 市場・競合・価格・収益 |
| [`docs/coconala_ops_workflow.md`](docs/coconala_ops_workflow.md) | 受注後の作業フロー詳細 |

## ソフト作戦（やること）

**画面版（おすすめ）:** ブラウザで順番にボタンを押すだけ。

```bash
python -m pip install -r requirements.txt
python3 -m streamlit run tools/pdf_job/app.py
```

1. 案件タブで作成 → 2. PDFタブでアップロード → 3. 列設定 → 4. 抽出 → 5. 納品ダウンロード

画面名は **構造くん**（青緑の書類ワークスペース）。タブ切替で直感操作できます。

コマンド版（予備）も同じ処理です。手順は `docs/beginner_runbook.md`。

練習用PDF:

```bash
python -m tools.pdf_job.make_sample_pdf
```

## 最初に売るもの（1本）

- **何を:** 文字選択できるPDFの表を、集計できる Excel + CSV にする
- **誰に:** 請求明細・報告書・統計表を今すぐ集計したい人
- **いくら:** 初回3枠のみ **3,000円**（通常表示 4,980円）
- **範囲:** 5ページ・1ファイル・列構成1種類・修正1回

1,500円帯の手入力競争には入らない。競馬専門としては出さない。  
`jobs/` 配下のお客様データは Git に上がりません。
