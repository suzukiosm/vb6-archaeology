# AGENTS.md — vb6-archaeology

**VB6 を壊さず理解するオペレーティングシステム（キット）。** 正本ツリーへの書込を禁止したまま、
VBP を切り出し・棚卸し・深読み・証拠つき理解まで進める。

人間向けランディング: [`README.md`](README.md)（English）· [`README.ja.md`](README.ja.md)（日本語）。対象は VB6 であり VBA ではない（[`docs/vb6-not-vba.md`](docs/vb6-not-vba.md)）。

## Setup

- Python **3.10+**（標準ライブラリのみ。pip 依存を増やさない）
- 単一入口: `python -m tools <command>`（`python tools/<name>.py` も動く）
- コマンド一覧: `python -m tools --help`

## Commands

| 作業 | コマンド | Cursor command |
|---|---|---|
| 5 分デモ | `python -m tools demo` | — |
| VBP 切り出し | `python -m tools extract "<vbp>"` | `/vb6-extract` |
| 構成レポート | `python -m tools inventory <extract_dir>` | `/vb6-inventory` |
| End 数照合 | `python -m tools verify <inventory.json>` | `/vb6-verify-reports` |
| 名前集合照合 | `python -m tools verify-names --inventory <inventory.json>` | `/vb6-verify-reports` |
| show_style 照合 | `python -m tools verify-show --inventory <inventory.json>` | `/vb6-verify-reports` |
| Form / Module 深読み | `python -m tools deep-read <FILE> --extract <dir>`（`.frm` / `.bas` / `.cls`） | `/frm-deep-read` |
| 実行時座標 | `python -m tools layout --extract <dir>` | `/runtime-layout` |
| 理解 tick | `python -m tools comprehend --add-tick <Proc>` · `--unticked` / `--suggest` | `/vb6-comprehend` |
| 報告書 | （skill `vb6-accurate-reports`） | `/vb6-report` |
| 再実装抜粋 | `python -m tools excerpt` · serve /excerpt | — |
| 横断 I/O | `python -m tools io-catalog` | `/vb6-io-catalog` |
| パイプライン進捗 | `python -m tools status` | `/vb6-status` |
| キットバックログ | `python -m tools ideas` | — |
| レポート閲覧 | `python -m tools serve` | `/serve-reports` |
| 設定検証 | `python -m tools config-check` | — |
| 自己点検 | `python -m tools smoke` | `/kit-smoke` |

`verify` / `verify-names` / `verify-show` は別照合（同じ `/vb6-verify-reports` から入る）。`--mode` には統合しない。

## Testing

キットを変更したら次を緑にする（CI も同じ入口）:

```powershell
python -m tools smoke
# 消費者リポで業務テストを後段追加しているとき、キット層だけ:
python -m tools smoke --kit-only
```

フィクスチャパイプライン（config-check → extract → inventory → verify → deep-read →
layout → comprehend → excerpt → io-catalog → status → verify-names → serve --live-get → scan-chars）＋ `tools/` 配下の unittest。
失敗時は stdout のステップ名を見て `CONTRIBUTING.md` · `tools/README.md` を参照（専用ログファイルは無い）。
再実装の製品面チェック: `docs/reimplementation-handoff.md`。

## DO NOT

- `protected_source_dirs`（キット既定 `source/`）へ**書込・移動・改名・削除しない**。hooks が拒否する
  - 例外は `python -m tools fixture`（= `tools/make_fixture.py`）のみ
- **Cursor `Read` で化けた日本語を根拠にしない**。VB6 テキストは CP932。内容判断は `python -m tools lines` か Python 経由
- 推定（役割・呼び出し・業務意味）を**証拠なしで書かない**。正規表現一括の callgraph は作らない
- inventory に無いファイル名・プロシージャ名をレポートに書かない（`comprehend --add-tick` は拒否する）
- 使い捨て `working/_*.py` を増やさない。足りなければ **`tools/` を改定して再実行**する
- 「100%」「done」はチェックリスト達成のみ。アプリ全体理解と混同しない
- レポート HTML を `file://` で開かない（`python -m tools serve`）

## セッション開始時の Read 順

毎回は 1–2。3 は対象アプリがあるとき。4 はキット保守のときだけ。詳細は `docs/ai-onboarding.md`。

1. 本ファイル（`AGENTS.md`）— 入口・規約・索引
2. [`docs/ai-onboarding.md`](docs/ai-onboarding.md)（必読・詳細）
3. 対象アプリがあるなら消費者の `docs/ai-dev-context.md`
4. キット自体を直すときだけ [`docs/kit-dev-context.md`](docs/kit-dev-context.md)

## 正典の層（文書が食い違うときの優先）

矛盾したら上の行を採用する。列「信頼できる情報源」がその層の正本パス。

| 優先 | 目的 | 信頼できる情報源 | 補足 |
|---|---|---|---|
| 1 | VB6 コード事実 | `working/extracts/<stem>/` | 正本は `source/` 等・読取専用。分析は抽出コピーを見る |
| 2 | 調査フロー・範囲 | `docs/flow/_master.md` | 工程順序・不変条件 |
| 3 | 消費者アプリのセッション事実 | `docs/ai-dev-context.md` | 現状・次手。新規は `docs/templates/` から |
| 4 | 入口・規約・索引 | 本ファイル（`AGENTS.md`） | 長い現状は ai-dev-context へ |
| 5 | 方法論（事実/推定の切り方） | `.cursor/rules/vb6-analysis.mdc` · `docs/methodology.md` | 手順の正は層2 |

キット保守メモは層3ではない → `docs/kit-dev-context.md`。

## ディレクトリ早見

| パス | 役割 |
|---|---|
| `source/` | 読取専用の VB6 正本（キット既定。別名は config で指定） |
| `working/extracts/` | VBP 切り出しコピー（分析用） |
| `working/reports/` | inventory / deep_read / comprehension 等 |
| `working/skeletons/` | Form skeleton JSON（再実装に渡す中間成果） |
| `tools/` | 再利用解析 + CLI（`python -m tools`） |
| `docs/` | 方法論・採用手順・テンプレ |
| `schema/` | `archaeology.config.json` の JSON Schema |
| `.cursor/` | rules / skills / commands / hooks |
| `archaeology.config.json` | 保護ディレクトリ名・出力先・`geometry_hints` / `mdi_chrome` / `layout_sub_scores` 等 |

## 標準サイクル

**検証 → 理解 →（任意）実装**

1. `/vb6-extract` — 正本から `working/extracts/<stem>/`
2. `/vb6-inventory` — 事実のみの構成正
3. `/frm-deep-read` · `/runtime-layout` — Form 深読み・実行時座標
4. `/vb6-comprehend` — 証拠つき tick 理解
5. `/vb6-report` — 報告書の作成・訂正（`excerpt` · `/vb6-verify-reports`）
6. （任意）消費者リポで再実装。確定事実のみ反映（製品面は `docs/reimplementation-handoff.md`）

詳細: `docs/workflow.md` · ツール索引: `tools/README.md`

## 由来・条件

方法論とコアツールは `VB6_source`（作業指示書再実装リポ）で培ったものを汎用化。
アプリ固有ツール（伝票 DAT・Form7 条件等）は本キットに含めない。
利用・複製は [LICENSE](LICENSE)（source-available・許諾前提）に従う。
キット保守・公開方針のメモは [`docs/kit-dev-context.md`](docs/kit-dev-context.md)。

## Learned User Preferences

- 「プッシュまで」はコミットとプッシュの両方を含む。コミット／プッシュは明示依頼があるときだけ行う。
- キット保守中は消費者リポへ書かない。参照は読取のみ。
- キットの主体は道具（`tools/`）としての完成度。README の発見性や星獲得向けの宣伝は従。
- LICENSE（source-available）はユーザーの明示なしで変えない。

## Learned Workspace Facts

- 主な消費者リポは `Z:\_Python\VB6_source`（作業指示書）と `Z:\_Python\delivery_slip`（納品書Ⅱ）。
- 公開リモートは `https://github.com/suzukiosm/vb6-archaeology`。
- Linguist は `.gitattributes` で `linguist-language=vb6`。引用符付き `"Visual Basic 6.0"` は git が属性として壊す。
