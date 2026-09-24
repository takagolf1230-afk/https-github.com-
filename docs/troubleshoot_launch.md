# 構造くんができないとき

## まずこれだけやってください（完全版）

1. このZIPをダウンロード（中に `tools` が入っています）  
   https://github.com/takagolf1230-afk/https-github.com-/raw/cursor/coconala-listing-docs-33f2/dist/kouzokun_windows.zip

2. ZIPを右クリック → **すべて展開**

3. できた **`kouzokun`** フォルダを開く

4. **`1_FIRST_SETUP.bat`** をダブルクリック

5. デスクトップの **`Kouzokun`** をダブルクリック

---

## よくある原因

### A. `tools` フォルダが無い（いちばん多い）
起動用の `.bat` だけあって、`tools` が無いと動きません。  
送っていただいた一覧に `tools` が無い場合は、この状態です。上の完全版ZIPを使ってください。

正しいフォルダには次があります:
- `1_FIRST_SETUP.bat`
- `start_kouzokun.bat`
- `tools` フォルダ
- `requirements.txt`

### B. Pythonが無い
黒い窓に `Python が見つかりません` と出たら:

1. https://www.python.org/downloads/
2. インストール時に **Add python.exe to PATH** にチェック
3. PC再起動
4. もう一度 `1_FIRST_SETUP.bat`

### C. デスクトップにアイコンが無い
`1_FIRST_SETUP.bat` か `create_desktop_shortcut.bat` を実行すると、  
デスクトップに **`Kouzokun.bat`** を作り、フォルダを自動で開きます。

それでもデスクトップに無いとき:
1. `kouzokun` フォルダをエクスプローラーで開く
2. **`start_kouzokun.bat`** を直接ダブルクリック  
   （デスクトップ無しでも起動できます）

OneDriveのデスクトップを使っているPCでも動くようにしてあります。

### D. ショートカットが作れなくても起動はできる
展開フォルダの **`start_kouzokun.bat`** を直接ダブルクリックすれば起動します。

---

## まだダメなとき
黒い窓に出た **エラー全文** を写真かコピペで送ってください。  
「できない」だけだと原因を特定できません。
