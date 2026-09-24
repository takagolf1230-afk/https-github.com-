# デスクトップから起動する手順（Windows）

最終更新: 2026-09-24

## いちばん簡単な流れ

0. まだPCにフォルダが無い人は、先にZIPをデスクトップへ展開  
   https://github.com/takagolf1230-afk/https-github.com-/archive/refs/heads/cursor/coconala-listing-docs-33f2.zip  
   （詳しくは [`where_is_it.md`](./where_is_it.md)）

1. 展開したフォルダを開く  
2. **`create_desktop_shortcut.bat`**（または `デスクトップにショートカットを作る.bat`）をダブルクリック  
3. デスクトップにできた **「構造くん」** をダブルクリック

以後はデスクトップのアイコンだけで起動できます。

## ファイルの役割

| ファイル | 役割 |
|---|---|
| `構造くんを起動.bat` | ソフト本体を起動（ブラウザで画面を開く） |
| `デスクトップにショートカットを作る.bat` | デスクトップにアイコンを1回作る |

## 初回だけ必要なもの

- Windows
- Python 3（[python.org](https://www.python.org/downloads/)）  
  インストール時に **Add python.exe to PATH** にチェック

初回起動時は部品の自動インストールで少し時間がかかります。  
起動後はブラウザで `http://localhost:8501` が開きます。

## 止め方

黒い窓（コマンド画面）で `Ctrl + C` を押すか、窓を閉じる。

## うまくいかないとき

| 症状 | 対処 |
|---|---|
| Python が見つかりません | Python を入れ直し、PATH にチェック |
| 画面が開かない | 10秒待ってからブラウザで `http://localhost:8501` を開く |
| ショートカットが無い | `デスクトップにショートカットを作る.bat` を再実行 |

関連: [`beginner_runbook.md`](./beginner_runbook.md)
