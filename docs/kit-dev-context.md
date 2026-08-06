# キット開発コンテキスト — vb6-archaeology 自体

**これはキット保守用。** 個別 VB6 アプリのセッション事実ではない。  
アプリ側は `docs/templates/ai-dev-context.md` → 消費者の `docs/ai-dev-context.md`。

## 1. ゴール

VB6 を壊さず理解するための汎用 OS（docs / .cursor / tools）を維持し、消費者リポへ移植可能にする。  
利用・複製は [LICENSE](../LICENSE)（許諾前提）に従う。

## 2. 現状（事実）

- 単一入口: `python -m tools <command>`（`tools/cli.py` の `COMMANDS` が正。個別 `python tools/<name>.py` も維持）
- コアツール: extract / inventory / verify_inventory / verify_report_names / frm_deep_read / runtime_layout / comprehension_scaffold / reimpl_excerpt
- 設定検証: `schema/archaeology.config.schema.json` + `lib/config_schema.py`（stdlib のみ）
- 自己点検: `kit_smoke.py`（config-check → fixture パイプライン → comprehend → excerpt → verify-names → scan-chars + unittest）· CI: ubuntu/windows × Python 3.10/3.13
- 補助: `frm_lines.py` · `scan_control_chars.py` · `frm_deep_read_all.py`（`deep_read_name_map`）
- `frm_deep_read`: .frm 単体解析注記、`show_style`、GoTo 飛び越え文候補（I/O·Call 等）+ ラベル地図、`ancestor_hidden`（静的近似・断定しない）
- `runtime_layout`: Show 文脈は Sub 境界で `recent_shows` クリア。開経路スコアは `layout_sub_scores`（既定 `form_load` / `mdiform_load` のみ）。MDI chrome は `mdi_chrome`（キット既定空）
- フィクスチャ: `source/mini_vbp/`（`make_fixture.py`・日本語 Caption・隠れた Frame 配下 Label 含む CP932）
- hooks: 保護ディレクトリへの書込拒否（キット既定名は `source/` のみ。別名は消費者 config）。`make_fixture.py` のみ shell allowlist
- AI 起動順: `AGENTS.md` → `docs/ai-onboarding.md`

## 3. 次手（キット）

- （採用済 2026-08-06 · mdi_chrome）`shell_forms` / `control_names` を config 化。`MDIForm1`·Picture1/FG1/fg2 のハードコードを撤去
- （採用済 2026-08-06 · GoTo）飛び越え候補の一般化 + ラベル地図 + tick/frm-audit 手順。デッド確定はしない
- （採用済 2026-08-06 · delivery_slip 実戦）inventory `show_style`/`show_calls` · 再実装ハンドオフ · `product_ui_notes` · CURRENT · data-guards · `smoke --kit-only` · deep-read `show_style` · `excerpt`/`serve /excerpt`。**未採用**: Show 完全 callgraph · Next/UI 同梱
- （採用済）消費者向け frm-audit テンプレ — `docs/templates/frm-audit.md` · `frm-audit-skill.md`（任意レーン。キット必須コマンドにはしない）
- （採用済）`layout_sub_scores` — 開経路 Sub スコアを config 化。アプリ固有名は消費者 config のみ
- （採用済）`tools/verify_report_names.py` — inventory 名集合 ↔ レポート言及。`/vb6-verify-reports` の正。End 数は `verify_inventory.py` のまま
- （採用済・参考）vbSpec 由来の事実層: `Class=` / シグネチャ / `Object=`・Version メタ / 任意 `--skip-parent-common`。コメント仕様書化は非採用
- （還元済 2026-07-29）消費者からの `ancestor_hidden` · Sub 境界 `recent_shows` · `frm_lines` / `scan_control_chars` / 一般化 `frm_deep_read_all`
- （還元済 2026-08-04 · VB6_source 監査）`frm_deep_read` 出力キー=VB_Name+`deep_read_name_map` · `verify_report_names`（allowlist/declares/EVENT_SUFFIX）· `picture1_height_by_sub` · chrome 正規化（現在は `mdi_chrome` config）。伝票・Form7·Next.js 監査は DO NOT PORT
- （還元済 2026-08-05→06）`frm_deep_read` GoTo — Open のみ → `find_goto_skipped_stmts` 一般化 + ラベル地図（compat: `find_goto_skipped_opens`）

### 2026-08-06 還元サマリ（10 行以内）

入れた: ハンドオフ · show_style · GoTo 一般化 · excerpt(+GoTo件数) · sessionStart layout · data-guards · `smoke --kit-only` · **`mdi_chrome` config**（シェル/chrome 名のハードコード撤去）· README/directory-layout/glossary 等の文書同期。  
入れなかった: Show 完全 callgraph · Next/CSS/業種ドメイン。キットは証拠・名前・保護・手順に留める。


## 4. 触ってよい／いけない

| 領域 | 規則 |
|---|---|
| `source/`（フィクスチャ含む） | 読取専用。再生成は `python -m tools fixture` のみ |
| `tools/` · `docs/` · `.cursor/` | キット改良の主戦場 |
| `working/` | スモーク成果。コミットしない（gitignore） |

## 5. 公開・運用方針（キット保守）

- 公開ドキュメント（README・LICENSE）に個人名を出さない。著作権表記は会社名義「有限会社アイコー」のみ
- README の License 節は `See [LICENSE](LICENSE).` に留め、詳細は LICENSE 側
- ハードコードの絶対パスを残さない。手順はプレースホルダ（`<this-repo>` 等）
- git は force push を避け、安全手順で進める
- 著作権者・連絡先: 有限会社アイコー（https://www.aiko1123.com/）。source-available（OSS ではない）
- GitHub リモート: `https://github.com/suzukiosm/vb6-archaeology`、既定ブランチ `main`（`protect-main` で force-push・削除禁止）
- 自己点検の正: `python -m tools smoke`（CI も同入口）
- バージョンの正: `tools/__init__.py` の `__version__`（`CHANGELOG.md` の最新タグと一致させる）
- 保護 hooks は `tools/test_hooks.py` が回帰を見る。hooks を変えたらここも更新する
