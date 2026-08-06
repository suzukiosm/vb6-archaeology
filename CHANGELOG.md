# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are exposed by `python -m tools --version` (`tools/__init__.py`).

## [Unreleased]

### Added

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
- smoke での serve `/excerpt` live GET（unittest のみ）

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
