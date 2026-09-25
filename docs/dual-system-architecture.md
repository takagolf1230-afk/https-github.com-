# デュアル運用: 現行は固定、新予想は別系統

## 決定事項

- **今使っている予想システムは変更しない**（印・買い目・運用フローそのまま）
- **新しい予想システムは別系統で新規構築**する
- 両方とも **同じ JRA公式データ（`jv_data.db` / JV-Data）を読む**
- 当面は並行運用し、成績を並べて比較する
- 新系統が安定して勝るまで、現行を置き換えない

```text
jv_data.db (JRA公式・読み取り専用)
        │
        ├──────────────┐
        ▼              ▼
  [現行システム]    [新予想システム]
  ※触らない          ※このリポジトリで新規
  印・券種・運用そのまま
        │              │
        └──────┬───────┘
               ▼
        比較レポート（的中・回収・見送り）
```

---

## 役割分担

| | 現行 | 新系統（本リポジトリ） |
| --- | --- | --- |
| 目的 | いまの実戦・実験の継続 | 厳選＋印＋券種可変＋回収ゲート |
| 変更 | **禁止**（バグ修正以外） | 自由に改善 |
| データ | 既存の読み方 | JV `RA/SE/HR/O1-O6` を `--db` で読む |
| 印 | 現行ロジックのまま | 機械印（◎○は勝ちきり、△は残る力） |
| 馬評価 | 複勝特化（変更しない） | **勝ちきり条件抽出→出走馬照合** |
| レース選別 | 現行のまま | `race_pattern` + ケン |
| 券種 | 現行のまま | T1〜T7 |
| オッズ床/EV | 現行のまま | 新系統のみ必須 |

---

## 新系統に入れるもの（調査で固まった仕様）

設計ドキュメント（実装の正）:

1. [jra-official-data-source.md](jra-official-data-source.md) … 公式データ対応
2. [required-data-for-selection.md](required-data-for-selection.md) … 必須A〜D
3. [imitate-successful-tipsters.md](imitate-successful-tipsters.md) … 真似する型
4. [tipster-pattern-mapping.md](tipster-pattern-mapping.md) … 印・軸・T1〜T7
5. [keiba-data-prediction-survey.md](keiba-data-prediction-survey.md) … 全体方針

新系統の処理順:

```text
1. --db から出走・過去走を読む
2. 勝ちきり条件を集計し、今走条件と出走馬を照合 → win_score
   （place/dark は別スコア）
3. race_pattern（Solid / AxisEdge / Mid / Chaos）
4. 印付け（◎○▲←win、△←place、☆←dark）
5. テンプレ T1〜T7
6. odds_floor / EV でケン
7. 買い目出力（現行と別ファイル）
8. 確定後に的中・回収を集計し、現行と比較
```

勝ちきり照合の詳細: [win-condition-matching.md](win-condition-matching.md)

---

## 評価指標: RPM-10 は変えない

現行・X（Twitter）で使っている **RPM-10 はそのまま継続**する。

| | RPM-10 | 新系統の追加KPI |
| --- | --- | --- |
| 対象 | 現行運用・X公開 | `next/` 内部検証・比較用 |
| 変更 | **しない** | 的中率 / 回収率 / 見送り率 / 券種別 などを併記 |
| 役割 | 対外・現行のものさしを固定 | 新系統の良し悪しを測る別ものさし |

運用ルール:

- Xに出す成績・説明の軸はこれまで通り RPM-10
- 新系統が良くても、RPM-10 の定義・計算・公開形式は勝手に置き換えない
- 比較するときだけ「RPM-10（現行）vs 新KPI（next）」を並べる
- 将来、新系統を主軸にする場合でも、RPM-10 を廃止するかは別判断（継続推奨）

---

新系統を現行の代わりにする条件（仮）:

- 同一期間・同一投資上限で比較
- **見送り込み**の回収率が現行以上
- Passレース的中率が極端に落ちていない
- サンプル目安: 最低50 Passレース、理想は数開催以上
- 一発高配当だけで勝っている場合は不採用

それまでは:

- 実戦の主軸 = 現行
- 新系統 = ペーパー or 少額並行

---

## リポジトリ配置

```text
docs/                 … 設計（共用）
next/                 … 新予想システム専用コード（現行と隔離）
  README.md
  pyproject / パッケージ
  …（実装をここに追加）
```

現行 Logic Horse（`lh_axis_flow_sim.py` 等）が別場所にある場合も、**そちらは編集しない**。  
新系統から現行コードを import して改変しない。読み取り専用で結果CSVを比較するだけにする。

---

## 実装の最初のマイルストーン

| Step | 内容 | 現行への影響 |
| --- | --- | --- |
| M0 | 設計ドキュメント（済） | なし |
| M1 | `next/` DB接続・スキーマ検出・CLI（済） | なし |
| M2 | 勝ちきり条件抽出＋照合 → win_score / 機械印（済・骨格） | なし |
| M3 | race_pattern + T1〜T7 買い目（済・骨格） | なし |
| M4 | odds_floor / EV ケン（済・骨格） | なし |
| M5 | 現行結果との比較レポート | なし（読み比べのみ） |

実データ接続:

```bash
cd next
PYTHONPATH=. python3 -m keiba_next inspect --db /path/to/jv_data.db
PYTHONPATH=. python3 -m keiba_next predict --db /path/to/jv_data.db --date YYYYMMDD
```
