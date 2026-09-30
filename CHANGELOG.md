# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are exposed by `python -m tools --version` (`tools/__init__.py`).

## [Unreleased]

### Added — AI index (review follow-up, phase 2)

- `python -m tools index` — inventory と extract から `<index_dir>/<stem>/`（既定 `working/index`）に `manifest.json` と `symbols` / `occurrences` / `effects` / `chunks` の JSONL を出す。記録の形は `schema/index.schema.json`（schema_version 1）
  - `symbols`: ファイル・手続き・Declare・Const・Enum（メンバー）・Type・Event・モジュール変数・コントロールに安定 ID（`<file>#<Kind>:<name>`）
  - `occurrences`: 既知の名前の字句上の出現と、VB6 のスコープ規則で選んだ候補（`basis`: `same_file` / `global` / `qualified` / `typed_variable` / `me`）。呼び出しグラフではない（ローカル変数の隠蔽は見ない。`resolution` が `unique` / `ambiguous`）
  - `effects`: ファイル文・レジストリ・`CreateObject` の ProgID・`New` の型・DB メソッド候補・SQL で始まる文字列リテラル・Shell・Declare 呼び出し・Show / Load / Unload / MsgBox / PopupMenu・Printer・SendKeys・`End`（業務意味なし）
  - `chunks`: 手続き単位（＋宣言部・デザイナ）のコードを物理行番号つきで、文脈ヘッダ・VB6 の注意（`On Error Resume Next`・Option Explicit なし・省略時 ByRef・既定メンバー・Static・`#If`）・副作用・一意に解決した参照・`sha256`・トークン見積もりと一緒に
- 設定 `index_dir`（schema に追加）
- `python -m tools bundle <Proc>[@File]` — 索引から 1 手続きの文脈束をトークン予算内で出す（コード → VB6 の注意 → 副作用 → 参照先の要約 → 参照元候補 → 宣言部 / デザイナ → 参照先のコード。入らなかった節は「Omitted」に列挙）。`--json` 可
- `python -m tools lines <file> --proc <Name>` — inventory と同じ規則の手続き範囲だけを行番号つきで出す
- `verify` が共通の字句器を使わない独立検査を足す: 物理行の素朴な正規表現による手続きヘッダ数（食い違いは `warnings` の `independent_header_count`）、手続き範囲の逆転・重なり（`mismatches`・exit 1）、同じファイル内の同名同種（`duplicate_procedure` 警告。多くは `#If` 分岐）
- tick の錨: `comprehend --add-tick` が `<report>.ticks.jsonl` に対象・範囲・範囲のソースの SHA-256 を残す。`comprehend --stale` が、ソースが変わった tick（`changed`）・手続きが消えた tick（`missing`）・錨の無い tick（`unanchored`）を一覧する（書込なし）。`--force` で骨格を作り直すと錨も消える
- `verify-names` がバッククォート内の一般識別子（`` `CalculateInvoiceTotal` `` 等）も inventory の名前（手続き・変数・定数・Enum メンバー・コントロール・ラベル・引数・型）と照合する。既定は警告（`unknown_identifiers`・exit 0）、`--strict` で失敗。以前はイベント風の名前とファイル名だけで、存在しない一般 Sub 名を素通りさせていた

### Fixed — review follow-up, phase 0 (2026-09-30)

- 解析キャッシュのキーにパーサコードの指紋（SHA-256）を含める。版番号を上げ忘れた編集でも古い事実を返さない。inventory JSON に `provenance`（`parser_version` / `parser_fingerprint`）を出す。PARSER_VERSION inv-13
- 保護 hooks が Windows の Cursor 上で実際には効いていなかった。Cursor は hook 入力を UTF-8 BOM 付きで渡し、`json.loads` が読めずに `allow` へ落ちていた（`cursor.hooks` ログで確認）。入力を `sys.stdin.buffer` から `utf-8-sig`（UTF-16 も可）で読み、読めないときは `protect_source` が deny、`guard_shell` が ask にする（`hooks.json` の `failClosed` と一致）。拒否理由には長さと先頭バイトだけを出す
- イベントの持ち主判定を `lib/event_binding.py` に一本化した。deep-read は固定のイベント名一覧だけを見ていたため、`Form_QueryUnload` / `Form_Initialize` / `MSComm1_OnComm` / `Winsock1_DataArrival` などを `unobserved`、そのコントロールを `code_ref: false` と誤っていた（inventory はイベント扱い）。持ち主（デザイナのコントロール・自モジュール `Form` / `UserControl` / `Class` / `PropertyPage` / `UserDocument` / `DataEnvironment` / `DataReport`・WithEvents 変数）の `<owner>_<event>` で判定し、inventory の手続きに `event_binding`（`designer` / `self` / `withevents`）、`.bas` / `.cls` の表面 skeleton にも同じ持ち主を出す。持ち主のいないイベント風の名前（`Ghost_Click`）は従来どおり `unobserved`
- VB6 はファイル番号の `#` を省略できる（`Open f For Input As fnum` / `Get fnum, , rec` / `Close fnum`）。io-catalog と deep-read の GoTo 飛び越え候補がこれを取りこぼしていた。ファイル文の認識を `lib/file_statements.py` に共通化（`#` 無し形は文頭か `Then` / `Else` 直後だけ。`rs.Open` / `rs.Close` / `Property Get` は拾わない）。io-catalog の対象は従来どおり 5 種
- `comprehend --suggest` が `Startup="Sub Main"` の起点を出さなかった。標準モジュールの `Sub Main` を理由 `startup_main` で先頭に出す
- deep-read の呼び出し観測が手続きごとに全文を字句解析し直していた（400 手続き・16,804 行の合成 Form 1 本で 90 秒）。識別子トークン集合を 1 回だけ作る方式にし、同じ判定のまま 0.5 秒。Show / Load の持ち主探しも二分探索にした
- 保護 hooks の抜け穴を塞いだ: パス比較を大文字小文字無視（`Source\` も保護）、fixture の許可はコマンド全体一致のみ（`;` / `&&` の連結は対象外）、`Copy-Item` / `cp` / `xcopy` / `robocopy` / `mkdir`、`git checkout|restore|clean|reset|stash…`、`[IO.File]::Write…` を変更系として扱う。`test_hooks.py` は Cursor と同じ BOM 付き入力で hook を動かす

### Changed — lexer follows MS-VBAL (review follow-up, phase 1)

- コメント末尾の ` _` は次の物理行もコメントにする（[MS-VBAL] `comment-body` は行継続を含む）。以前は次の行をコードとして扱い、VB6 が実行しない文を I/O 等として拾っていた。飲み込まれた行は inventory の `diagnostics`（`comment_continuation`）と MD / HTML の「診断」に出る
- `Else:` / `Loop:` 等の予約語はラベルではなく文。数値の行ラベル（`10 Print x` / `20:` / 行番号だけの行）を `kind=label` にする
- 識別子の先頭に非 ASCII 文字を許す（日本語の Sub / Function / Const / Enum / Type / Event 名、Show / Load 対象）
- `#If` / `#ElseIf` / `#Else` / `#End If` / `#Const` を評価せず領域として出す（inventory `conditional_compilation`、手続きの `conditional`）。同じ名前・種別の重複定義は `diagnostics`（`duplicate_procedure`）
- `Event Changed`（括弧なし）を拾う。Enum メンバーの値（`value`）と `[_Hidden]` 名を残す
- 実 VB6 の `.cls` では Instancing と既定プロパティが常に `null` だった。IDE は `Instancing =` 行を保存せず、既定メンバーは手続き内の `Attribute Value.VB_UserMemId = 0` で書く。表面に `class_header`（`BEGIN`/`END` の生値。翻訳しない）、手続きに `attributes`（`VB_UserMemId` / `VB_Description` / `VB_MemberFlags` / `VB_ProcData.*`）、表面に `default_member` / `enumerator_member`（`-4`）/ `member_attributes`（変数の `VB_VarUserMemId` 等）。fixture `Widget.cls` を IDE 保存形式の `BEGIN` ブロックにし、`Ready` を既定メンバーにした

### Added — declarations (review follow-up, phase 1)

- inventory のファイル項目に `variables`（モジュールレベルの `Public` / `Private` / `Global` / `Dim` / `WithEvents`。1 宣言子 1 件。`Dim a, b As Long` の `a` は Variant）と `options`（`explicit` / `base` / `compare` / `private_module` / `deftypes`）。型は VB6 の規則で機械的に解決し、根拠を `type_source`（`as` / `suffix` / `deftype` / `default`）に残す。MD / HTML に「Option Explicit なし」を明示
- 手続きに `params_detail`（`passing` は省略時 `ByRef`、`passing_explicit`・`optional`・`default`・`param_array`・`is_array`・解決済み `type`）と、Function / Property Get の `return_type` / `return_type_source`。宣言の分解は `lib/declarators.py`
- `Function Calc$(ByVal n As Long)` のように型文字付きの名前で引数と戻り値が落ちていた。`type_suffix` を分けて読む
- 外部依存: VBP の `Reference=` を inventory の `references`（`typelib` は GUID・版・LCID・パス・説明、`project` は `.vbp` パス）に載せる（以前は extract の生文字列だけ）。`objects` に `guid` / `version`。`Declare` に `alias` / `params` / `returns` / `params_detail` / `return_type`。`.frm` 等の先頭 `Object = "{…}"; "X.OCX"` を `ocx_objects`、`VB.` 以外のコントロールを `external_control_classes`（件数つき）。fixture VBP に `stdole2.tlb` の Reference

### Added — error handling and statement-based GoTo (review follow-up, phase 1)

- inventory の手続きに `error_handling`（`on_error_resume_next` / `on_error_goto_0` / `on_error_goto_minus1` / `on_error_goto`+`target` / `resume` / `resume_next` / `resume_label` / `err_raise` を行順に）と `labels`。フロー解析はしない。無い手続きにはキーを出さない
- deep-read の GoTo / ラベル地図と飛び越え候補を文単位にした。物理行の正規表現では `ErrH: MsgBox …`（同じ行に文が続くラベル）と `x = 1: GoTo Done`（コロン連結の GoTo）を落とし、飛び越え候補が 0 件になっていた。GoTo と同じ行の後続文、数値行ラベルへの GoTo も扱う

### Changed — shared designer parser (review follow-up, phase 1)

- 以下フェーズ 1 の出力形の変更で PARSER_VERSION inv-14

- デザイナの `Begin … End` を `lib/designer.py` に一本化し、inventory と deep-read が同じ木を読む。`BeginProperty` 内の `Caption` / `Width` が親コントロールを上書きしていた（例: Toolbar のボタン名がツールバーの Caption になる）。`""` を含む Caption が途中で切れていた
- deep-read のコントロールに `props`（型付けしない生プロパティ）・`data_binding`（`DataSource` / `DataField` / `RecordSource` / `DatabaseName` / `ConnectionString` …）・`frx_refs`（`$"F.frx":0000` 等。中身は読まない）・`property_blocks`（値があるときだけ）。座標・可視性・並び順は従来と同じ（fixture で旧出力と一致を確認）
- inventory の `controls` に `line` / `parent` / `index`、ファイルに `data_bindings`

### Fixed — review regressions (2026-09-30)

- Extract path manifest and collision preflight; inventory no longer follows parent references outside extracts.
- Comment continuations, named arguments, numeric date/time literals, and false Show/I/O hits in strings.
- Shared procedure extraction for inventory/deep-read; unresolved event owners no longer imply dead code.
- Accessor-specific Property ticks (`--kind`) and conservative compatibility for old notes.
- Verification rejects missing VBP files; parser cache inv-12 includes encoding configuration.

### Added

- `python -m tools readable` — extract の UTF-8 サイドカー（物理行一致。extract は触らない。`.frx` 等はスキップ）。Cursor Read 用。分析の正は extracts。`readable_dir`（既定 `working/readable`）
- `python -m tools demo` — フィクスチャの extract → inventory → excerpt → serve。tick しない。`serve --live-get` とは別
- 公開ランディングを英語 `README.md` + 日本語 `README.ja.md` に分け、`docs/en/`（encoding · VB6≠VBA · adopting 要約）とフィクスチャ画面 `docs/assets/` を追加。Linguist は `.gitattributes` で `.bas`/`.frm` 等を `vb6`（Visual Basic 6.0）とし VBA と混ぜない
- inventory の VBP メタに `Type` / `CondComp` / `CompatibleMode` / `CompilationType` / `CompatibleEXE32` / `AutoIncrementVer` を生文字列で残す。モジュール表面に `vb_predeclared_id`（bool | null）と `vb_user_mem_id`（int | null）。解釈しない。PARSER_VERSION inv-8
- `lib.vbparse` — `_` 折り後に文字列外の `:` で文分割（`iter_statements` / `split_colon_statements`）。io-catalog / verify `count_ends` / layout / inventory が同じ規則。到達判定なし。行番号は物理。`#If`・数値行番号・DATA の `:` は既知制限
- `Me.Show` / 単独 `Show`（target は `Me` / 空。Form に結び付けない）を `show_calls` に載せる。`Load` / `Unload` は `lifetime_calls`（転置しない）。PARSER_VERSION inv-9
- inventory `parse_procedures` / `parse_declarations` が `iter_statements`。`x = 1: End Sub` で End 照合が揃う。PARSER_VERSION inv-10
- `parse_surface` が `iter_statements`。`Const A = 1, B = 2` を複数件（文字列・括弧内のカンマは値に残す）。PARSER_VERSION inv-11
- `python -m tools ideas` — `docs/kit-improvement-ideas.md` の open / adopted / deferred / wont を集計（キットバックログの正。Issues は受付口）
- `deep-read` / `deep-read-all` が `.bas` / `.cls` の表面レポート + skeleton（Implements / GoTo / Show 文面。Form chrome なし）。fixture `SkipOpen`
- `python -m tools verify-show` — inventory と deep-read の `show_style` 照合。同じ行の食い違いは exit 1。inventory だけの Show（デッド Sub）は警告。どちらが正かは決めない。fixture `Ghost_Click`
- `test_make_fixture.py` — mini_vbp の回帰契約（UserControl · `On Error GoTo` · `GoSub` · 前方 GoTo 越し Open · I/O 5 種）。temp へ書いてパーサで見る（`source/` は触らない）

### Changed

- `tools/README.md` を英日同一ファイルにし、コマンド要約は `python -m tools --help`（`cli.py` COMMANDS）を正とする
- deep-read の一般 Sub は呼び出し未観測を `unobserved` / `unobserved_reason=no_caller_observed` と書く（到達不能ではない）。orphan のみ `dead` / `dead_reason`。`optional_assign_markers` キット既定空。`show_map` は `unobserved` を旧 `dead` と同じく除外

### Fixed

- `serve` が既定ポート占有時に黙死していた。空きポートへフォールバックし、実際の URL を flush して印刷する。失敗時は `next: python -m tools serve --port <free-port>`
- レポート HTML（inventory / excerpt / serve ランディング / comprehension）をライトテーマ固定。ダークモードで表が空欄に見えないようにする
- 未観測 Sub の理由キーを `dead_reason` から分け、`docs/kit-improvement-ideas.md` の「入方向の転置と進捗が無い」死文を消した
- Windows（`core.autocrlf=true`）の clone で `fixture` / `smoke` を回すと、中身が同じ `source/mini_vbp/` の 7 ファイルが変更扱いになっていた。`.gitattributes` の `source/mini_vbp/** -text` で git にフィクスチャのバイト列（CP932・LF）を変換させない。既に変更扱いの clone は一度 `git add source/mini_vbp` で消える（内容差分は無い）

## [0.2.0] - 2026-08-16

0.1.0 以降の調査サイクルを版にした。handoff / `show_style` / GoTo 一般化 / `mdi_chrome` / excerpt に加え、進捗・転置・追加ファイル種・I/O カタログ・メニュー木・`.cls` layout・同伴バイナリ・serve live-get を含む。`python -m tools --version` は `0.2.0`。

### Added

- `__version__` と `CHANGELOG.md` 最新日付見出しの照合（`tools/lib/version.py` · `test_version.py`）
- `python -m tools serve --live-get` — 一時ポートで `/` と `/excerpt` を GET（200 必須）。smoke が `serve --check` の次に実行
- extract の同伴コピーを一般化（`.frm`→`.frx` · `.ctl`→`.ctx` · `.pag`→`.pgx` · `.dob`→`.dox` · `.dsr`→`.dsx`）。中身は解析しない。fixture `MiniCtl.ctx`
- `runtime_layout` が `.cls` も走査（`.bas` と同列）。fixture `Widget.PlaceHost` が `Form1.Left = 50`
- deep-read skeleton `menu_tree` — メニューの親子・Caption・Visible/Enabled（デザイナ値）。実行時 `Enabled =` は layout（混ぜない）。`menu_warnings` は維持。fixture `mnuFile` / `mnuOpen` / `mnuHidden`
- `python -m tools io-catalog` — extract 内の `Open` / `Kill` / `Name` / `Get` / `Put` を file:line で列挙（業務意味なし）。既存 skeleton の `goto_skipped_stmts` と突合。fixture `IoDemo` + `Form_Load` 前方 GoTo 越し `Open`
- deep-read ラベル地図に `On Error GoTo` / `GoSub`（kind `on_error` / `gosub`）。飛び越えスパンは前方 GoTo のみ。デッド確定しない
- inventory / excerpt の Module/Class 表面 — Implements · WithEvents · Instancing（生整数）· 公開 Property。PARSER_VERSION inv-7。deep-read は複製しない
- excerpt の Module / Class 表面 — 未 tick の `.bas`/`.cls` と `Declare` 件数（DLL 意味は書かない）
- `serve` の `/` ランディング — inventory · comprehension · excerpt · layout · deep-read へのリンク + ディレクトリ一覧。`file://` 禁止は維持
- `python -m tools comprehend --unticked` / `--suggest` — 未 tick の CLI 一覧。`--suggest` はヒューリスティック（自動 tick しない）。空なら「未 tick 0」
- inventory が `UserControl=` / `PropertyPage=` / `UserDocument=` / `Designer=` / `RelatedDoc=` / `ResFile32=` を棚卸し（PARSER_VERSION inv-6）。`.ctl` 等はデザイナ解析、`.res` は一覧のみ。fixture `MiniCtl.ctl`
- inventory / excerpt の「Show 文の転置（事実）」— 既存 `show_calls` の逆引き。inventory に無いターゲットは `unresolved`。呼び出しグラフではない
- `python -m tools status` — 既存成果物の有無・件数（3 行 + JSON）。推定・次手は出さない。sessionStart が同じ 3 行を出す
- `verify` が `working/reports/<stem>_verify.json` を残す（status が読む。再実行はしない）
- `docs/kit-improvement-ideas.md` — キット保守の未採用バックログ（事実の穴 + 優先提案。完全 callgraph / Next / 業種は対象外のまま）
- `mdi_chrome` — `shell_forms` / `control_names` を config 化（キット既定は空）。layout の MDI chrome 分類・Bare 正規化・`mdiDefaults` フォールバックシェルを消費者 config だけで合わせられる
- `docs/reimplementation-handoff.md` — 調査完了と製品 UI 完了のギャップ用チェックリスト · `show_style`（`mdi_child` / `modal_overlay` / `navigate`）の精読メモ規約
- comprehension tick 任意欄 `product_ui_notes`（テンプレ + `comprehend --add-tick` 骨格 HTML）
- `docs/templates/CURRENT.md` — 長セッション手渡し正本（調査 Stop / 製品 UI Stop の対応）
- `docs/templates/consumer-data-guards.example.md` — 本番データ書込抑止 hooks 例（プレースホルダ）
- `docs/adopting-in-a-project.md` — データ I/O ミラー方針 · smoke 層 · delivery_slip 由来の実戦ノート
- `python -m tools smoke --kit-only` — 消費者拡張時にキット層だけ回すためのフラグ（キット本体の既定動作と同じ）
- inventory Form に `show_style` / `show_calls` / `mdi_child`（事実スキャン。呼び出しグラフではない。PARSER_VERSION inv-5）
- excerpt — Form 単位の GoTo 飛び越え件数（skeleton）+ `unknown`≠navigate 注記。sessionStart に `/runtime-layout`
- `frm_deep_read` — GoTo 飛び越え候補を Open 以外のファイル I/O · Call · Shell · Load/Unload · MsgBox に一般化（`find_goto_skipped_stmts`）。 Sub 内 GoTo/ラベル地図を追加。いずれも候補・断定しない
- deep-read `show_style` 候補（`MDIChild`→`mdi_child` / `Show vbModal`→`modal_overlay`。素の Show は `unknown`。skeleton `show_style` + `show_map[].calls`）
- `python -m tools excerpt` + `serve` `/excerpt` — Form 一覧 · Show 関係 · 未 tick の再実装向け抜粋
- mini_vbp fixture — `Form12.Show vbModal` · Form12 `MDIChild=-1`（回帰用）
- （履歴）GoTo 飛び越えは当初 Open のみ → 現在は `find_goto_skipped_stmts`（I/O·Call 等）+ ラベル地図に一般化。compat: `find_goto_skipped_opens`
- `protected_path_markers` — どこに現れても読取専用にするパス断片。**正本がリポ外にある構成**（共有ドライブ上の VB6 ツリー）を一級市民として扱う。`extract` と両 hooks が同じ設定を読む（`tools/test_config.py`）
- `default_extract` — `--extract` 省略時に使う extract 名。複数プロジェクトを抱える消費者が、ツール 3 本にフォルダ名をハードコードせずに済む
- `scan_roots` / `scan_skip_dirs` — scan-chars の走査対象を config 化。**保護ディレクトリとマーカーは自動 skip**（`source` のハードコードを解消）
- `mdi_defaults` — 消費者専用キー。設定時のみ `runtime-layout.json` に `mdiDefaults` を出す
- `form_layout_gap.md` の「着手」列を再生成時に保持（生成物の中の人手記述を壊さない原則を layout にも適用）
- 寛容な dispatch — `python -m tools <cmd>` が `main(argv)` と旧来の `main()` の両方を受ける。旧シグネチャのツールを多数抱える消費者が、CLI 導入のためだけに全ツールを書き換えずに済む

### Changed

- `runtime_layout` — `MDIForm1` / Picture1 / FG1 / fg2 のハードコードを撤去し `mdi_chrome` を参照
- `protected_source_dirs` の空配列を正当な設定として扱う（従来は `["source"]` に戻していた）。schema も `minItems` / `default_source_dir` の必須を外した
- `extract` の正本ルートは `--source-root` 未指定かつリポ内に保護ディレクトリが無いとき `.vbp` の親を使う
- `workflow.md` Step 8 — 再実装ハンドオフへのリンクを追加
- 文書同期 — README / AGENTS / directory-layout / glossary / anti-patterns / methodology / QUICKREF / CONTRIBUTING を excerpt · `mdi_chrome` · handoff に揃える

### Fixed

- 非 CP932 コンソール（英語 Windows の cp1252 等）で日本語 Caption を出力すると `UnicodeEncodeError` で停止していた。各 CLI が `lib/console.py` の `enable_utf8_stdio()` で stdout/stderr を UTF-8 に切り替える（回帰: `tools/test_console.py`）。新 CI マトリクスの windows ジョブが検出

### Deferred（意図的に未実装）

- inventory 横断の「誰が誰を Show するか」完全グラフ（Form 単位の show_style/show_calls 事実スキャンは採用済）
- Next.js / デザインシステム / 業種ドメインの同梱

## [0.1.0] - 2026-08-05

最初のタグ付きリリース。調査サイクルの入口を単一 CLI に統一し、設定・保護機構・理解レポートを機械検証の対象にした。

### Added

- `python -m tools <command>` — 全ツール共通の入口（`tools/cli.py` · `tools/__main__.py`）。`python tools/<name>.py` も従来どおり動く
- `python -m tools serve` — レポートを 127.0.0.1 で配信（手作業の `http.server` を置換）
- `python -m tools config-check` + `schema/archaeology.config.schema.json` — 設定の型・未知キーを標準ライブラリのみで検証（`tools/lib/config_schema.py`）
- `python -m tools comprehend` — comprehension レポートの骨格生成と tick 追記。**inventory に無い名前は拒否**し、既存の記述は上書きしない（`tools/comprehension_scaffold.py`）
- `/runtime-layout` command + skill `vb6-runtime-layout` — 実行時座標を deep-read から独立したステップに
- `tools/test_hooks.py` — 保護 hooks（deny / ask / allowlist / 偽陽性）の回帰テスト
- `tools/test_cli.py` · `tools/test_config_schema.py` · `tools/test_comprehension_scaffold.py`
- `.github/` — issue テンプレ（バグ・改善提案）· PR テンプレ · CODEOWNERS
- `tools/kit_smoke.py` — fixture パイプライン + unittest の単一検証入口
- GitHub Actions CI (`.github/workflows/ci.yml`)
- `CONTRIBUTING.md` · `SECURITY.md`
- `docs/README.md` — documentation hub
- `picture1_height_by_sub` / `verify_report_allow_files` config（消費者向け・キット既定は空）
- fixture `BackupDay.frm`（stem ≠ VB_Name）で deep_read out_key を回帰検知

### Changed

- `AGENTS.md` — 実行コマンドと DO NOT を先頭に置く構成へ再編（agents.md の慣習に合わせる）
- kit_smoke — config-check / deep-read-all / comprehend / serve --check / scan-chars を追加し、CLI 経由で実行
- CI — ubuntu / windows × Python 3.10 / 3.13 のマトリクス（CP932 と Windows パスの回帰を実際に踏む）
- `.cursor/commands/*.md` — 全 command に YAML frontmatter（name / description）を追加
- 全ツールの入口を `main(argv)` に統一し、CLI エラーメッセージを英語へ統一
- `archaeology.config.json` — `$schema_comment` を実際の `$schema` 参照へ
- 採用ガイド・テンプレ — グローバルルール（`_core.mdc`）に依存しないことを明記
- README — Python 要件・検証一行・License 節を GitHub 慣習に整理
- `docs/directory-layout.md` · `docs/templates/project-local.mdc` — 現行構成に同期
- `frm_deep_read.py` — 出力キーをファイル stem から VB_Name + `deep_read_name_map` へ（VB6_source と契約一致）
- `verify_report_names.py` — declares / allowlist / EVENT_SUFFIX / Exit Sub 誤検知除外
- `runtime_layout.py` — `resolve_picture1_form` · fg1/fg2 chrome 正規化（アプリ Form 名ハードコードはしない）
