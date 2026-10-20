# Split View

Windows で、見ている窓を左半分に寄せ、右半分に [Gemini](https://gemini.google.com/app) を開く小さなボタンです。Python は不要です。

## ダウンロード

[最新の Release](https://github.com/takayuki-shi-ai88/SplitView/releases/latest) から `SplitView.zip` を取り、中の `SplitView.exe` をダブルクリックしてください。

Windows のスマートスクリーンが出たら「詳細情報」→「実行」を選んでください。署名のない exe のため、初回だけこの確認が出ます。

## 使い方

1. `SplitView.exe` をダブルクリックする
2. 画面右下付近に角丸の **Split View** ボタンが出る
3. 見たいアプリを前面にして、ボタンをクリックする  
   → 左半分にその窓、右半分に Gemini

- ドラッグ … ボタンの移動（分割はしない）
- Esc … ボタンを閉じる
- 初回起動で、デスクトップとスタートアップにショートカットを作ります（Windows にログインしたあともボタンが出ます）

exe と同じフォルダに `overlay-state.json` が1つできます。ボタンの位置と、いま動いているかどうかの記録です。消しても次の起動で作り直されます。

## 動作環境

- Windows 10 / 11
- 受け取る側に Python は不要

## ソースから exe を作り直す

1. Python 3 を入れる
2. `build_exe.bat` を実行する
3. できた `配布用\SplitView.exe` を使う

## 構成

| 場所 | 内容 |
|---|---|
| `src/` | アプリ本体 |
| `配布用/` | コピーして渡すフォルダ |
| `LICENSE` | MIT |
