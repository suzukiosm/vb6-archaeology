# Contributing

**[English](#english)** · **[日本語](#japanese)**

This repository is source-available. Viewing and learning are welcome. Use, copy, modify, redistribute, or embed only with a grant under [LICENSE](LICENSE).

This kit is **Visual Basic 6**, not VBA. See [docs/en/vb6-not-vba.md](docs/en/vb6-not-vba.md).

## English

### Invariants

- No writes, moves, renames, or deletes under `protected_source_dirs` (kit default `source/`)
- Exception: `python -m tools fixture` (`tools/make_fixture.py`)
- Do not add one-off `working/_*.py`; extend `tools/`
- Inferences need evidence. No regex-wide call graph

### Dev environment

- Python **3.10+**, standard library only
- Windows and Linux. Examples may use PowerShell; `python -m tools` is the same
- CI: ubuntu / windows × Python 3.10 / 3.13 runs `python -m tools smoke`

### Pull requests

1. One theme per PR (do not mix a tool change with a drive-by docs sweep)
2. Green `python -m tools smoke` before opening
3. Fill `.github/PULL_REQUEST_TEMPLATE.md`
4. Behavior change → `[Unreleased]` in `CHANGELOG.md`. Cutting a release moves that block to `## [X.Y.Z] - YYYY-MM-DD` and sets `tools/__init__.py` `__version__` (`test_version.py` checks)
5. Changes to `AGENTS.md`, `.cursor/**`, `schema/**`, `archaeology.config.json` need review (`.github/CODEOWNERS`)

Public English docs live in `docs/en/` and `README.md`. Japanese operator docs stay in `docs/` and `README.ja.md`. Keep both landings in sync when the 5-minute path or the VB6≠VBA claim changes. `tools/README.md` is bilingual in one file; command summaries stay in `cli.py` `COMMANDS`.

---

## 日本語

本リポジトリは source-available です。利用・複製・改変・再配布・組込の前に [LICENSE](LICENSE) に従い許諾を得てください。対象は **VB6** であり VBA ではありません（[docs/vb6-not-vba.md](docs/vb6-not-vba.md)）。

## 不変条件

- `archaeology.config.json` の `protected_source_dirs`（キット既定 `source/`）へは書込・移動・改名・削除禁止
- フィクスチャ再生成のみ例外: `python -m tools fixture`（= `tools/make_fixture.py`）
- 使い捨て `working/_*.py` を増やさず、足りない抽出・検証は `tools/` を改定する
- 推定（役割・呼び出し・業務意味）は証拠必須。正規表現一括の callgraph は作らない

## 開発環境

- Python **3.10+**（標準ライブラリのみ。追加 pip 依存なし）
- Windows / Linux いずれも可。ローカル手順の例は PowerShell 表記
- CI は ubuntu / windows × Python 3.10 / 3.13 で `python -m tools smoke` を実行

## PR の出し方

1. 変更は 1 テーマに絞る（ツール改定とドキュメント整理を混ぜない）
2. `python -m tools smoke` を緑にしてから出す
3. `.github/PULL_REQUEST_TEMPLATE.md` のチェックを埋める（不変条件・検証・ドキュメント同期）
4. 挙動が変わるなら `CHANGELOG.md` の `[Unreleased]` に追記する。版を切るときは `[Unreleased]` を `## [X.Y.Z] - YYYY-MM-DD` へ移し、`tools/__init__.py` の `__version__` を同じ番号にする（`test_version.py` が照合する）。キット保守の未採用案の正は `docs/kit-improvement-ideas.md`（`python -m tools ideas`）
5. `AGENTS.md` · `.cursor/**` · `schema/**` · `archaeology.config.json` の変更はレビュー必須（`.github/CODEOWNERS`）

公開向け英語は `README.md` と `docs/en/`。日本語ランディングは `README.ja.md`。5 分手順や VB6≠VBA の主張を変えたら両方を揃える。

## 検証

変更後は次を緑にしてください。

```powershell
python -m tools smoke
# 消費者リポで業務テストを後段追加しているとき、キット層だけ:
python -m tools smoke --kit-only
```

（フィクスチャパイプライン + `tools/` 配下の unittest。CI も同じ入口です。）

ツールを追加したときは `tools/cli.py` の `COMMANDS` と `tools/README.md` のコマンド名表を同時に更新してください
（`test_cli.py` が全コマンドの `main`・`--help`・README の `` `name` `` を検証します）。

## 変更の置き場

| 領域 | 規則 |
|---|---|
| `tools/` · `docs/` · `.cursor/` · ルート入口 | キット改良の主戦場 |
| `working/` | スモーク成果。コミットしない |
| `source/` | 読取専用（上記例外のみ） |

ドキュメントを変えたら、関連する `AGENTS.md` / `docs/` / `tools/README.md` / commands を矛盾なく同期してください。

## エージェント向け

1. `AGENTS.md` → `docs/ai-onboarding.md` を Read
2. 定型作業は `/vb6-extract` 等の commands、または対応 skill から入る
3. キット保守メモは `docs/kit-dev-context.md`
