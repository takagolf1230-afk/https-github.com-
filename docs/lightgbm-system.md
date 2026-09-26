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

## 特徴量

着順は「この馬が勝ったか」という学習ラベルにだけ使う。予想の入力は、今走より前の走と今走の条件から作る複数ファクターで、今走の着順・タイム・確定オッズは入れない。

| グループ | 名前 |
| --- | --- |
| 過去の勝ちきり | `n_starts` `win_rate` `rentai_rate` `place_rate` `inv_avg_finish` `same_jyo_win_rate` `same_dist_win_rate` `same_track_win_rate` `same_jyo_rentai_rate` `same_dist_rentai_rate` `same_track_rentai_rate` `win_over_place` |

連対率は2着以内の割合。重みは勝率、連対率、複勝率の順。3着止まりは連対に数えない。モデルを作り直すときは `train` をやり直す（特徴の本数が変わっている）。
| 今走との条件差 | `days_since_last` `dist_delta` `same_track_last` `umaban_norm` `field_size` `futan` `same_jockey` |
| 前走の内容 | `last_agari` `last_weight` `weight_delta` `last_corner_pos` |

上がりは `HaronTimeL3` / `Agari`、馬体重は `BaTaiju`、増減は `ZogenSa`、斤量は `Futan`、騎手は `KisyuCode`、通過は `Jyuni1c`〜`Jyuni4c`。列が無いDBではその因子は 0 のまま学習する。列名が違うときは `inspect` の出力で合わせる。

## 的中率特化

全レースの `top1_hit_rate` と、見送り後の `pass_hit_rate` を分ける。

```bash
PYTHONPATH=. python3 -m keiba_next backtest --db /path/to/jv_data.db --until 20260101 --model out/ranker.txt --min-gap 0.15
```

`--min-gap` 未満のスコア差（1位と2位）は見送り。`n_pass` と `pass_hit_rate` が見送り後の的中率。既定の `0` は全レースを母数にする。回収は見送ったレースを投資に入れない。

## 検証

`backtest` は `--until` より前だけで学習し、その日以降のレースでスコア1位の単勝的中率を出します。回収率は行に `TanOdds` があるときだけ計算します。

実データの `jv_data.db` はこの開発環境には無いので、バックテストの実行は手元のDBパスで行います。

## まだ後で足すもの

- 券種別の回収率（払戻テーブル HR のワイド・三連系との結合）。単勝は `verify` で馬番一致を見ている
- 実ファイル `jv_data.db` での `train` / `backtest`（この環境にはDBが無い）
