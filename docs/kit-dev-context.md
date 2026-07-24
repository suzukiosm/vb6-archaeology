# キット開発コンテキスト — vb6-archaeology 自体

**これはキット保守用。** 個別 VB6 アプリのセッション事実ではない。  
アプリ側は `docs/templates/ai-dev-context.md` → 消費者の `docs/ai-dev-context.md`。

## 1. ゴール

VB6 を壊さず理解するための汎用 OS（docs / .cursor / tools）を維持し、消費者リポへ移植可能にする。  
利用・複製は [LICENSE](../LICENSE)（許諾前提）に従う。

## 2. 現状（事実）

- コアツール: extract / inventory / verify / frm_deep_read / runtime_layout
- フィクスチャ: `source/mini_vbp/`（`make_fixture.py`・日本語 Caption 含む CP932）
- hooks: 保護ディレクトリへの書込拒否（config 駆動）。`make_fixture.py` のみ shell allowlist
- AI 起動順: `AGENTS.md` → `docs/ai-onboarding.md`

## 3. 次手（キット）

- `runtime_layout.py` 内の Show 経路ヒューリスティック（特定 Form 名分岐）をさらに設定化
- inventory ↔ レポート名集合照合の定型ツール化
- 消費者初回採用フィードバックの反映

## 4. 触ってよい／いけない

| 領域 | 規則 |
|---|---|
| `source/`（フィクスチャ含む） | 読取専用。再生成は `python tools/make_fixture.py` のみ |
| `tools/` · `docs/` · `.cursor/` | キット改良の主戦場 |
| `working/` | スモーク成果。コミットしない（gitignore） |
