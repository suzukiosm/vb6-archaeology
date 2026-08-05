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
| 8 | PowerShell `-replace` / `Set-Content` で日本語ファイルを壊す | エディタツールまたは Python `encoding="utf-8"` で targeted 置換 |
| 8b | PowerShell 二重引用符内のバッククォートで Markdown を壊す（`` `F ``→FF・`` `v ``→VT） | バルク文字列を PS に載せない。混入検知は `python -m tools scan-chars`（hits=0） |
| 9 | 到達不能 Form を必須機能扱い | 証拠を残して除外 or Dev 専用と明記 |
| 9b | `frm_deep_read` のイベント 0 を孤立・到達不能と即断する | 本ツールは .frm 単体解析。他 .frm/.bas からの `Show` / 操作は見えない |
| 9c | 親 Frame/PictureBox が `Visible=0` かつコード未参照なのに子孫を必須 UI にする | `ancestor_hidden` を確認し実行時非表示相当として扱う |
| 9d | deep-read の Open 列挙をソース順＝実行順と読む（GoTo 飛び越しを無視） | 「GoTo で飛び越えられる Open（候補）」節を確認。条件付き GoTo でもその分岐では Open に届かない |
| 10 | 完了を信用して再監査しない | gap 再監査を定例化 |
