# 素人向け：受注したらこの順で押すだけ

最終更新: 2026-09-23

このリポジトリの道具を使うと、難しいことは「列の対応を画面で書く」だけになります。  
Pythonの中身を覚える必要はありません。

**おすすめは画面版（UI）です。** コマンド版は予備です。

---

## 最初に1回だけ（PCセットアップ）

```bash
cd （このリポジトリ）
python -m pip install -r requirements.txt
```

### 画面を開く（おすすめ）

```bash
python -m streamlit run tools/pdf_job/app.py
```

ブラウザが開いたら、画面の案内どおり

1. 案件を作る  
2. PDFをアップロード  
3. 列を設定  
4. 抽出  
5. 納品ダウンロード  

まで進めます。

### コマンドで動作確認（予備）

```bash
python -m tools.pdf_job.make_sample_pdf
python -m tools.pdf_job new --name practice
# できた jobs/日付_practice/01_input/ に samples/sample_invoice.pdf をコピー
python -m tools.pdf_job check --job （フォルダ名）
python -m tools.pdf_job extract --job （フォルダ名）
python -m tools.pdf_job deliver --job （フォルダ名）
```

`03_delivery/成果物.xlsx` が開けばOKです。

---

## ココナラで受注したあとの手順（毎回）

### 1. 案件フォルダを作る

```bash
python -m tools.pdf_job new --name お客様名
```

例: `jobs/20260923_tanaka/`

中身:

| フォルダ/ファイル | 用途 |
|---|---|
| `00_intake.md` | ヒアリングメモ |
| `columns.yaml` | 依頼された列の定義（ここだけ編集） |
| `01_input/` | お客様PDFを置く |
| `02_work/` | 自動プレビュー（触らなくてよい） |
| `03_delivery/` | 納品する xlsx / csv |

### 2. PDFを置く

トークルームからダウンロードしたPDFを `01_input/` へ。

### 3. 文字が選べるか確認

```bash
python -m tools.pdf_job check --job 20260923_tanaka
```

- 「文字を選択できる」→ そのまま進む  
- 「選べません」→ スキャン。追加料金 or お断りを先に伝える

### 4. 依頼形式を `columns.yaml` に書く

お客様が「日付・品名・数量・金額で欲しい」と言ったら:

```yaml
pages: [1]   # 対象ページ。全部なら null
columns:
  - name: 日付
    source: ["日付", "年月日"]
    type: date
  - name: 品名
    source: ["品名", "商品名", "項目"]
    type: text
  - name: 数量
    source: ["数量", "個数"]
    type: number
  - name: 金額
    source: ["金額", "税込", "合計"]
    type: number
```

ポイント:

- `name` = 納品する列名（依頼どおり）
- `source` = PDFに書いてありそうな見出しの候補
- `type` = `text` / `number` / `date`

### 5. 表を抜き出す（プレビュー）

```bash
python -m tools.pdf_job extract --job 20260923_tanaka
```

`02_work/raw_preview.xlsx` を Excel で開き、見出しが `source` と合うか確認。  
合わなければ `columns.yaml` を直して、もう一度 extract。

### 6. 納品ファイルを作る

```bash
python -m tools.pdf_job deliver --job 20260923_tanaka
```

出るもの:

- `03_delivery/成果物.xlsx`（シート: data / review / log）
- `03_delivery/成果物.csv`

### 7. 目視（ここだけ手作業・必須）

1. `data` の先頭10行・末尾10行
2. 金額列の合計と元PDFの1ページ分をざっと突合
3. `review` に怪しい行がないか見る
4. 問題なければトークルームへ送る

`review` の見方（お客様への定型文）:

```
Excelの「review」シートは、読み取りや型変換で確認が必要だった箇所です。
空欄にしてごまかしていません。元PDFと突合してください。
```

---

## ソフト作戦の考え方（素人でも壊れない）

| やること | 人 | ソフト |
|---|---|---|
| 欲しい列を決める | あなた（ヒアリング） | columns.yaml |
| 表を抜く |  | extract |
| 日付・数値・全角半角を揃える |  | deliver |
| 重複行を落とす |  | deliver |
| 取れない箇所を残す |  | review シート |
| 最終の正しさ | **あなた（目視）** |  |

ソフトは「下ごしらえ」。納品責任は目視です。  
数値の創作はしません。読めないものは `review` に出ます。

---

## うまくいかないとき

| 症状 | 対処 |
|---|---|
| 表が空っぽ | スキャンの可能性 → check を再実行。必要なら手作業 or オプション |
| 列がずれる | raw_preview の見出しを見て source を直す |
| ページが多い | 5ページ超は追加料金。pages で対象を絞る |
| 列構成が2種類 | 別スキーマは別案件 or オプション。1回の deliver は1スキーマ |

---

## やってはいけない

- 自動出力を目視せず送る
- 元PDFにない数字を埋める
- 案件フォルダをGitに上げる（`jobs/` は無視設定済み）
- 1,500円の手入力や見た目コピーをこの道具で無理にやる

関連: [`coconala_ops_workflow.md`](./coconala_ops_workflow.md) / [`coconala_pdf_excel_listing.md`](./coconala_pdf_excel_listing.md)
