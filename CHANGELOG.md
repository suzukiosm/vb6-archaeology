# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are exposed by `python -m tools --version` (`tools/__init__.py`).

## [Unreleased]

### Added

- `protected_path_markers` — どこに現れても読取専用にするパス断片。**正本がリポ外にある構成**（共有ドライブ上の VB6 ツリー）を一級市民として扱う。`extract` と両 hooks が同じ設定を読む（`tools/test_config.py`）

### Changed

- `protected_source_dirs` の空配列を正当な設定として扱う（従来は `["source"]` に戻していた）。schema も `minItems` / `default_source_dir` の必須を外した
- `extract` の正本ルートは `--source-root` 未指定かつリポ内に保護ディレクトリが無いとき `.vbp` の親を使う

### Fixed

- 非 CP932 コンソール（英語 Windows の cp1252 等）で日本語 Caption を出力すると `UnicodeEncodeError` で停止していた。各 CLI が `lib/console.py` の `enable_utf8_stdio()` で stdout/stderr を UTF-8 に切り替える（回帰: `tools/test_console.py`）。新 CI マトリクスの windows ジョブが検出

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
