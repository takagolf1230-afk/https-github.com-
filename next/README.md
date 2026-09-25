# next/ — 新予想システム（現行とは別系統）

現行の予想システムは**一切変更しない**。  
ここは JRA公式データ（`--db jv_data.db`）を使う新系統専用。

## 方針

- 設計: `docs/dual-system-architecture.md`
- データ: JRA-VAN JV-Data のみ
- 出力: 現行と別パス（例: `next/out/`）
- 比較: 確定後に的中率・回収率を並べるだけ

## 予定モジュール

```text
next/
  keiba_next/          # パッケージ
    db.py              # JV DB 読み取り
    features.py        # 過去走スコア
    marks.py           # 印付け
    race_pattern.py    # Solid/AxisEdge/Mid/Chaos
    tickets.py         # T1〜T7
    gates.py           # odds_floor / EV
    backtest.py        # 検証
  README.md            # 本ファイル
```

## 使い方（予定）

```bash
python -m keiba_next.predict --db /path/to/jv_data.db --date YYYYMMDD
python -m keiba_next.backtest --db /path/to/jv_data.db --from YYYYMMDD --to YYYYMMDD
```

実装は M1（DB接続）から順に追加する。
