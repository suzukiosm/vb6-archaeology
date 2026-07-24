# アンチパターン（やってはいけない）

| # | アンチパターン | 代わりに |
|---|---|---|
| 1 | 正本を「整理」する | `working/extracts/` にコピーしてから触る |
| 2 | Caption だけで遷移を実装 | Show / Load / メニュー Enabled を精読 |
| 3 | 正規表現 callgraph を自動生成 | 読んだ Sub の呼び出しだけ記載 |
| 4 | inventory に無い Sub 名をレポートに書く | 先に inventory 更新 or 記述削除 |
| 5 | 「100%理解した」と宣言 | チェックリスト達成率だけ言う |
| 6 | `working/_*.py` を増やし続ける | `tools/` を改定 |
| 7 | Cursor Read の化け文字を原文引用 | Python CP932 デコード結果を使う |
| 8 | PowerShell `-replace` で日本語ファイルを壊す | エディタツールで targeted 置換 |
| 9 | 到達不能 Form を必須機能扱い | 証拠を残して除外 or Dev 専用と明記 |
| 10 | 完了を信用して再監査しない | gap 再監査を定例化 |
