# 別系統: LightGBM Ranker

この系統は **一着の予想に特化**する。複勝圏に残る馬を本命にしない。

- 学習ラベルは 1着だけ 1、それ以外は 0
- ◎はレース内スコアの1位
- バックテストはスコア1位が勝った割合
- 2着・3着の印（○▲△）は券種の相手用。軸の決定には使わない

## 役割

| | 現行 | この系統 |
| --- | --- | --- |
| エンジン | チャットAI | LightGBM `lambdarank` |
| 入力 | プロンプト + JSON | 過去走特徴のみ |
| オッズ | 最終予想に使用 | 特徴に入れない。床ゲートだけ |
| 出力 | 現行の印（複勝寄り） | **一着スコア1位を◎**。相手は印。T1〜T7 |
| 学習ラベル | — | 1着=1、2着以下=0（`lambdarank`） |

## コマンド

```bash
cd next
PYTHONPATH=. python3 -m keiba_next train --db /path/to/jv_data.db --until 20260101 --model out/ranker.txt
PYTHONPATH=. python3 -m keiba_next backtest --db /path/to/jv_data.db --until 20260101 --model out/ranker.txt
PYTHONPATH=. python3 -m keiba_next predict --db /path/to/jv_data.db --date YYYYMMDD --model out/ranker.txt
```

`--until` より前だけで学習し、その日以降で予想する（時系列分割）。

## 特徴量（現行版）

過去走のみ: 出走数、勝率、複勝率、平均着順の逆数、同場勝率、同距離帯勝率、勝率/複勝率。  
当該走の着順・確定オッズは入れない。

## 検証

`backtest` は `--until` より前だけで学習し、その日以降のレースでスコア1位の単勝的中率を出します。回収率は行に `TanOdds` があるときだけ計算します。

実データの `jv_data.db` はこの開発環境には無いので、バックテストの実行は手元のDBパスで行います。

## まだ後で足すもの

- 上がり・通過・枠・馬場の特徴
- 実DBの列名差の吸収
- 券種別の回収率（払戻テーブル HR との結合）
