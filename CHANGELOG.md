# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `tools/kit_smoke.py` — fixture pipeline + unittest の単一検証入口
- GitHub Actions CI (`.github/workflows/ci.yml`)
- `CONTRIBUTING.md` · `SECURITY.md`
- `docs/README.md` — documentation hub
- `picture1_height_by_sub` / `verify_report_allow_files` config（消費者向け・キット既定は空）
- fixture `BackupDay.frm`（stem ≠ VB_Name）で deep_read out_key を回帰検知

### Changed

- `AGENTS.md` — Testing 節を追加。セッション記憶（Learned）を `docs/kit-dev-context.md` へ移設
- README — Python 要件・検証一行・License 節を GitHub 慣習に整理
- `/kit-smoke` · `docs/ai-onboarding.md` — `kit_smoke.py` に寄せる
- `docs/directory-layout.md` · `docs/templates/project-local.mdc` — 現行構成に同期
- `frm_deep_read.py` — 出力キーをファイル stem から VB_Name + `deep_read_name_map` へ（VB6_source と契約一致）
- `verify_report_names.py` — declares / allowlist / EVENT_SUFFIX / Exit Sub 誤検知除外
- `runtime_layout.py` — `resolve_picture1_form` · fg1/fg2 chrome 正規化（アプリ Form 名ハードコードはしない）
