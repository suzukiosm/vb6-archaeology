# キット開発コンテキスト — vb6-archaeology 自体

**これはキット保守用。** 個別 VB6 アプリのセッション事実ではない。  
アプリ側は `docs/templates/ai-dev-context.md` → 消費者の `docs/ai-dev-context.md`。

## 1. ゴール

VB6 を壊さず理解するための汎用 OS（docs / .cursor / tools）を維持し、消費者リポへ移植可能にする。  
利用・複製は [LICENSE](../LICENSE)（許諾前提）に従う。

## 2. 現状（事実）

- コアツール: extract / inventory / verify_inventory / verify_report_names / frm_deep_read / runtime_layout
- 補助: `frm_lines.py` · `scan_control_chars.py` · `frm_deep_read_all.py`（`deep_read_name_map`）
- `frm_deep_read`: .frm 単体解析注記、`ancestor_hidden`（dead + Visible=0 コンテナ配下）
- `runtime_layout`: Show 文脈は Sub 境界で `recent_shows` クリア
- フィクスチャ: `source/mini_vbp/`（`make_fixture.py`・日本語 Caption・隠れた Frame 配下 Label 含む CP932）
- hooks: 保護ディレクトリへの書込拒否（キット既定名は `source/` のみ。別名は消費者 config）。`make_fixture.py` のみ shell allowlist
- AI 起動順: `AGENTS.md` → `docs/ai-onboarding.md`

## 3. 次手（キット）

- `runtime_layout.py` 内の Show 経路ヒューリスティック（特定 Form 名分岐・PREFERRED_SUB）をさらに設定化（Sub 境界クリアは済）
- 消費者向け frm-audit テンプレ（任意・後回し）
- （採用済）`tools/verify_report_names.py` — inventory 名集合 ↔ レポート言及。`/vb6-verify-reports` の正。End 数は `verify_inventory.py` のまま
- （採用済・参考）vbSpec 由来の事実層: `Class=` / シグネチャ / `Object=`・Version メタ / 任意 `--skip-parent-common`。コメント仕様書化は非採用
- （還元済 2026-07-29）消費者からの `ancestor_hidden` · Sub 境界 `recent_shows` · `frm_lines` / `scan_control_chars` / 一般化 `frm_deep_read_all`

## 4. 触ってよい／いけない

| 領域 | 規則 |
|---|---|
| `source/`（フィクスチャ含む） | 読取専用。再生成は `python tools/make_fixture.py` のみ |
| `tools/` · `docs/` · `.cursor/` | キット改良の主戦場 |
| `working/` | スモーク成果。コミットしない（gitignore） |
