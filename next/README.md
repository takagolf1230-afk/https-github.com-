# next/ — 新予想システム（現行とは別系統）

現行の予想システムは**一切変更しない**。  
ここは JRA公式データ（`--db jv_data.db`）を使う新系統専用。

## 方針

- 設計: `docs/dual-system-architecture.md`
- データ: JRA-VAN JV-Data のみ
- 出力: 現行と別パス（`next/out/`）
- 比較: 確定後に的中率・回収率を並べるだけ

## セットアップ

手元PCの手順は [docs/local-setup.md](../docs/local-setup.md)。  
Gemini / Claude / ChatGPT には [docs/dev-assistant-brief.md](../docs/dev-assistant-brief.md) を貼る。印は出させない。

```bash
cd next
python -m venv .venv
pip install -r requirements.txt
python -m keiba_next fixture --out out/fixture.db
python -m keiba_next ping --db out/fixture.db
```

実データ:

```bash
PYTHONPATH=. python3 -m keiba_next inspect --db /path/to/jv_data.db
PYTHONPATH=. python3 -m keiba_next train --db /path/to/jv_data.db --until YYYYMMDD --model out/ranker.txt
PYTHONPATH=. python3 -m keiba_next predict --db /path/to/jv_data.db --date YYYYMMDD --model out/ranker.txt
```

## モジュール

```text
keiba_next/
  db.py            # JV DB 読み取り・スキーマ検出
  course_key.py    # レース・競馬場条件キー
  win_match.py     # 勝ちきり照合 → win_score
  race_pattern.py  # Solid/AxisEdge/Mid/Chaos
  marks.py         # ◎○▲△☆
  tickets.py       # T1〜T7
  gates.py         # odds_floor / EV
  pipeline.py      # 1レース予想
  fixture.py       # 開発用ミニDB
  cli.py           # CLI
```

## テスト

```bash
cd next && PYTHONPATH=. python3 -m unittest tests.test_pipeline -v
```
