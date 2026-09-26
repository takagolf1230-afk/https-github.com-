# 別系統: LightGBM Ranker

現行 Logic Horse（LLMの①〜⑤）とは別システム。印は LightGBM が出す。

## 役割

| | 現行 | この系統 |
| --- | --- | --- |
| エンジン | チャットAI | LightGBM `lambdarank` |
| 入力 | プロンプト + JSON | 過去走特徴のみ |
| オッズ | 最終予想に使用 | 特徴に入れない。床ゲートだけ |
| 出力 | 現行の印 | レース内スコア → 印 → T1〜T7 |

## コマンド

```bash
cd next
PYTHONPATH=. python3 -m keiba_next train --db /path/to/jv_data.db --until 20260101 --model out/ranker.txt
PYTHONPATH=. python3 -m keiba_next predict --db /path/to/jv_data.db --date YYYYMMDD --model out/ranker.txt
```

`--until` より前だけで学習し、その日以降で予想する（時系列分割）。

## 特徴量（現行版）

過去走のみ: 出走数、勝率、複勝率、平均着順の逆数、同場勝率、同距離帯勝率、勝率/複勝率。  
当該走の着順・確定オッズは入れない。

## まだ後で足すもの

- 上がり・通過・枠・馬場の特徴
- 実DBの列名差の吸収
- 的中率・回収率のバックテスト（M5）
