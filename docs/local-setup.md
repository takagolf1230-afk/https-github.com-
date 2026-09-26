# 手元PCでの起動手順

現行の Logic Horse とは別フォルダです。予想の印は LightGBM が出し、Gemini / Claude / ChatGPT は開発の補助だけに使います。

## 1. デスクトップに新しいフォルダを作る

開発場所はデスクトップの `keiba-next` だけです。現行の Logic Horse のフォルダとは別にします。

ZIPをどこかに展開し、中の `setup-local.bat` をダブルクリックします。スクリプトがデスクトップに `keiba-next` を作り、そこへ一式を置いてから、仮想環境・パッケージ・サンプル起動まで進めます。以後の編集はこのフォルダで行います。

最初から git で置く場合:

```bat
cd %USERPROFILE%\Desktop
git clone https://github.com/takagolf1230-afk/https-github.com-.git keiba-next
cd keiba-next
git checkout cursor/keiba-hit-rate-survey-a9ec
setup-local.bat
```

`jv_data.db` は `keiba-next` の外に置きます。

## 2. Python

`setup-local.bat` を使った場合、この節は済んでいます。手で行うときは Python 3.10 以上です。

```bash
cd next
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. まずサンプルで動かす

DBが無くてもここまで確認できます。

```bash
cd next
python -m keiba_next fixture --out out/fixture.db
python -m keiba_next ping --db out/fixture.db
python -m keiba_next train --db out/fixture.db --until 20260901 --model out/ranker.txt
python -m keiba_next predict --db out/fixture.db --date 20260921 --model out/ranker.txt
python -m unittest discover -s tests -v
```

Windows で `python` が無いときは `py -3` に読み替えます。

## 4. 本番DB

JRA-VAN から作った `jv_data.db` のフルパスを渡します。このリポジトリにはDBを置かないでください。

```bash
python -m keiba_next inspect --db "C:\path\to\jv_data.db"
python -m keiba_next verify --db "C:\path\to\jv_data.db"
python -m keiba_next backtest --db "C:\path\to\jv_data.db" --until 20260101 --model out/ranker.txt --min-gap 0.15
python -m keiba_next predict --db "C:\path\to\jv_data.db" --date 20260921 --model out/ranker.txt
```

`inspect` がテーブル名エラーになったら、その出力を開発用チャットに貼って列名合わせを依頼します。

## 5. ローカルのCursorチャットへログを渡す

これまでの経緯は [cursor-dev-log.md](cursor-dev-log.md) にまとめてある。デスクトップの `keiba-next` を Cursor で開き、ローカルの新しいチャットでこのファイルを添付する。

クラウドのチャットごと移す場合は、エージェントの作業完了後に Agents ウィンドウで Move to → Local を選ぶ。実行中は出ない。

## 6. チャットAIの使い方

印を出させません。コードとエラーの相談だけです。新しいチャットの最初に [dev-assistant-brief.md](dev-assistant-brief.md) を貼ってください。

貼ってよいもの:

- `inspect` の JSON
- ターミナルのエラー全文
- `backtest` の `top1_hit_rate` と `pass_hit_rate`

貼らないもの:

- 馬券の最終判断を任せるプロンプト
- 最新オッズを渡して印を変えさせる指示
