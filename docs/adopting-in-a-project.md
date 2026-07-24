# 他リポへの採用ガイド

## 許諾前提（必読）

本キットは [LICENSE](../LICENSE) のとおり **source-available** であり、オープンソースではありません。  
閲覧・学習は歓迎しますが、**複製・改変・他リポへの組込・再配布には事前許諾が必要**です。

以下の手順は **許諾を得たあとの社内／契約範囲内** での採用手順です。

## 目的

`vb6-archaeology` を「調査 OS」として、個別アプリリポに載せる。

## コピーする最小セット

```
archaeology.config.json
AGENTS.md                    # 消費者向けに短く改稿可（長い現状は書かない）
tools/                       # 汎用 CLI 一式
.cursor/rules/
.cursor/skills/
.cursor/commands/            # アプリ固有 command は追加してよい
.cursor/hooks.json
.cursor/hooks/
docs/methodology.md
docs/workflow.md
docs/flow/_master.md         # アプリ目標に合わせて改稿
docs/ai-onboarding.md        # パスだけ合わせてよい
docs/templates/              # 初回コピー元
```

**コピーしないもの（このキットのサンプル）**

- `source/mini_vbp/`（フィクスチャ）
- `working/extracts|reports|skeletons` の中身
- `docs/kit-dev-context.md`（キット保守用。消費者のセッション事実ではない）

## 設定

`archaeology.config.json` の例（再実装あり）:

```json
{
  "protected_source_dirs": ["アイコー", "source"],
  "default_source_dir": "アイコー",
  "extracts_dir": "working/extracts",
  "reports_dir": "working/reports",
  "skeletons_dir": "working/web/src/lib",
  "geometry_hints": {
    "MDIForm1": { "left": 0, "top": 0, "height": 13550, "width": 0 }
  }
}
```

- キット既定の `skeletons_dir` は `working/skeletons`
- 再実装が `working/web/src/lib` に skeleton を置くなら上のように変更
- `geometry_hints` は親フォーム相対の実行時式を数値化するときだけ使う（任意）

## 初回セットアップ手順（エージェント向け）

1. 許諾済みであることを確認
2. 上記最小セットを消費者リポへコピー
3. `docs/templates/ai-dev-context.md` → `docs/ai-dev-context.md` を作成し、対象 VBP を記入
4. `docs/templates/project-local.mdc` → `.cursor/rules/project-local.mdc`
5. 正本を保護ディレクトリへ配置（または既存パスを `protected_source_dirs` に追加）
6. extract → inventory → verify を実 VBP で実行
7. `AGENTS.md` の入口表を消費者のレポートパスに合わせて更新

## アプリ固有ツールの置き場

- 汎用（どの VBP でも使う）→ キット側 `tools/` に還元を検討（許諾・還元ルールに従う）
- 固有（伝票 DAT・特定 Form）→ 消費者 `tools/` に置き、キットを汚さない

## 境界

| キット | 消費者 |
|---|---|
| 方法論・hooks・汎用抽出 | 業務知識・DAT 契約 |
| inventory / deep-read | 画面配線・UX 差分 |
| 事実レポートの型 | 「今どこまで終わったか」（`ai-dev-context.md`） |
