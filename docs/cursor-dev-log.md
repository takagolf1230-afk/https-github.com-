# ローカルCursorへ渡す開発ログ

このファイルが、クラウド側で進めた競馬予想システム開発のログです。ローカルの新しいチャットの最初に、このファイルを添付して「このログの続きから、デスクトップの keiba-next で開発して」と送ってください。

クラウド側のチャット自体を移す場合は、このエージェントの作業が終わったあと、Cursor の Agents ウィンドウでこのエージェントを開き、Move to → Local を選んでください。実行中は表示されません。先にこのリポジトリをローカルで開いた Agent が一つあると、Local が選べます。クラウドのチャットは Export Transcript では書き出せません。

## 開発場所

- フォルダ: デスクトップの `keiba-next`（現行 Logic Horse とは別）
- ブランチ: `cursor/keiba-hit-rate-survey-a9ec`
- 取得:

```bat
cd %USERPROFILE%\Desktop
git clone https://github.com/takagolf1230-afk/https-github.com-.git keiba-next
cd keiba-next
git checkout cursor/keiba-hit-rate-survey-a9ec
setup-local.bat
```

ZIPから始める場合は `setup-local.bat` を実行する。スクリプトがデスクトップに `keiba-next` を作る。`jv_data.db` はそのフォルダの外に置く。

## 確定した方針

- 現行の Logic Horse（LLMの①〜⑤、RPM-10、X投稿）は、新系統が並走比較で勝つまで変えない。
- 印・券種・見送りは数値モデルだけが出す。チャットAI（Gemini / Claude / ChatGPT / Cursor）は開発補助と説明だけ。印を上書きしない。
- データは JRA公式 JV-Data。`--db` で `jv_data.db` を読む。スクレイピングを主データにしない。
- オッズは購入ゲート（odds_floor / EV）だけ。学習特徴にも、印を変える理由にも使わない。
- 学習は `--until` より前。検証はその日以降。今走の着順・タイム・確定オッズは特徴に入れない。
- 一着特化。学習ラベルは1着だけ1、それ以外は0。◎はレース内スコア1位。
- 着順そのもので馬を決めない。勝率・連対率・複勝率（重みはこの順）に、間隔・距離差・馬場継続・馬番・頭数・上がり・馬体重・増減・斤量・同騎手・前走通過を加える。
- 連対率は2着以内。3着止まりは連対に数えない。
- 的中率特化。1位と2位のスコア差が `--min-gap` 未満のレースは見送り。指標は `pass_hit_rate`。既定の `0` は全レース。
- 券種はレース条件で固定しない。直線長は少点数、小回りは広め。軸は◎。相手は○▲△。☆は軸が固いときだけ。
- 合成オッズは後回し。`jv_data.db` はクラウド環境には無い。実集計は手元の `--db`。

## ここまで作ったもの

`next/keiba_next/` が新系統。

- `db.py` 公式DBの読み取りとスキーマ検出
- `course_key.py` 場・芝ダート・距離帯
- `win_match.py` モデルが無いときの照合。1着 > 連対 > 複勝
- `lgbm_model.py` LightGBM lambdarank。ラベルは一着のみ
- `lgbm_features.py` 上の多因子。特徴名は `FEATURE_NAMES`
- `race_pattern.py` `marks.py` `tickets.py` `gates.py` 型、印、T1〜T7、オッズ床
- `backtest.py` 時系列分割。`top1_hit_rate` と `pass_hit_rate`
- `cli.py` の `ping` `inspect` `fixture` `train` `backtest` `predict`

テストは `cd next` で次が成功済み（9件）。実DBでは未実行。

```bat
python -m unittest discover -s tests -v
```

## 手元で次にやること

1. `python -m keiba_next inspect --db "C:\path\to\jv_data.db"`
2. `python -m keiba_next verify --db "C:\path\to\jv_data.db"`
3. 列名が違えば `HaronTimeL3` `BaTaiju` `ZogenSa` `Futan` `KisyuCode` `Jyuni1c`〜`Jyuni4c` を実DBに合わせる
4. `train` してから `backtest --until YYYYMMDD --min-gap 0.15`
5. 特徴を足したあとは、必ず `train` からやり直す
6. Logic Horse との切替判断は、見送りを含む回収が現行以上になってから

```bat
cd next
.venv\Scripts\activate
python -m keiba_next train --db "C:\path\to\jv_data.db" --until 20260101 --model out/ranker.txt
python -m keiba_next backtest --db "C:\path\to\jv_data.db" --until 20260101 --model out/ranker.txt --min-gap 0.15
python -m keiba_next predict --db "C:\path\to\jv_data.db" --date YYYYMMDD --model out/ranker.txt
```

詳しい制約は `docs/dev-assistant-brief.md`。システムの説明は `docs/lightgbm-system.md`。起動手順は `docs/local-setup.md`。

## 続き: DBの読み取り照合

`verify` は EveryDB2 / JV-Data の SQLite を読み、次が一致するかを見る。

- テーブルは `N_RACE` / `N_UMA_RACE` / `N_HARAI` に加え、`x_RACE` 系も検出する
- 出馬表（データ区分2）と月曜確定（区分7）が両方ある馬は、確定行だけ残す。取消・除外・中止は出走馬から外す
- レースキーは文字の `09` と数値の `9` をゼロ埋めで結ぶ
- 1着の馬番が、払戻の月曜行 `PayTansyoUmaban1`（同着なら2・3も）と一致するか
- 過去走が当該日より前だけか
- `348` は上がり34.8秒、`999` は欠損、`560` は斤量56.0kg、`ZogenFugo` の `-` と `ZogenSa` で馬体増減

このクラウド環境には `jv_data.db` も `jv.data.db` も無かった。照合の動作確認は EveryDB2 形のサンプルDBで行い、テスト13件は成功している。実ファイルは手元のパスを `--db` に渡す。

```bat
cd next
.venv\Scripts\activate
python -m keiba_next verify --db "C:\path\to\jv_data.db"
```

`ok` が false のときは `mismatches` を開発チャットに貼る。列が足りないだけなら `columns.missing` を見る。学習特徴に単勝オッズは入れていない。`Odds` はバックテストの回収計算用にだけ小数へ戻す。
