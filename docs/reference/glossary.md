# 用語集

| 語 | 意味 |
|---|---|
| 正本 | ユーザーが渡した改変禁止の VB6 ツリー |
| 抽出 / extract | `working/extracts/<stem>/` の分析用コピー |
| inventory | VBP→ファイル→プロシージャの事実レポート |
| deep-read | `.frm` のライブ Ctrl・イベント・データパス等の機械+整理。`.bas`/`.cls` は表面レポート（Form chrome なし） |
| skeleton | 再実装用の Form コントロール座標 JSON（`menu_tree` = デザイナのメニュー親子） |
| runtime_layout | コード部が書き換える Left/Top/Visible 等のカタログ |
| mdi_chrome | config キー。MDI シェル VB_Name（`shell_forms`）と chrome コントロール名（`control_names`）。キット既定は空 |
| show_style | Show / MDIChild から出す再実装向け候補（`mdi_child` / `modal_overlay` / `unknown` 等）。機械は `navigate` を出さない |
| Show 転置 | 既存 `show_calls` の逆引き（誰がこの Form を Show しているか）。未解決は `unresolved`。呼び出しグラフではない |
| excerpt | Form · Module/Class（未 tick · Declare件数 · Implements / WithEvents / Instancing）· Show · GoTo件数 の短い HTML（`python -m tools excerpt` · serve `/excerpt`） |
| 表面（Module/Class） | inventory の Implements / WithEvents / Instancing（生整数）/ 公開 Property。deep-read ではない |
| serve ランディング | `serve` の `/`。inventory · comprehension · excerpt · layout · io-catalog · deep-read へのリンク + ディレクトリ一覧 |
| io-catalog | extract 横断の `Open` / `Kill` / `Name` / `Get` / `Put`（file:line。業務意味なし。GoTo 飛び越えと突合） |
| status | 既存成果物の有無・件数（`python -m tools status`）。推定も次手も出さない |
| tick | 理解の最小単位（主要 Sub 1 つの精読）。未 tick 一覧は `comprehend --unticked`。`--suggest` はヒューリスティックで自動 tick しない |
| GoTo 飛び越え候補 | 前方 GoTo が飛び越す I/O·Call 等。候補のまま。デッド確定にしない |
| 到達不能 | UI から開けない / 死んだメニュー等（証拠必須） |
| 保護ディレクトリ | hooks が書込を拒否するパス。キット既定名は `source/`（`archaeology.config.json` の `protected_source_dirs` で変更） |
| 消費者リポ | 本キットを採用して特定アプリを扱う側のリポジトリ |
