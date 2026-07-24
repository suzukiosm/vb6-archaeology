# AI Onboarding — 必読

このファイルは **本リポを開いたエージェントが最初に読む正**。  
推測で進めない。不明点はユーザーに確認する。

---

## 0. 30 秒で分かること

あなたは「VB6 考古学者 OS」のオペレータである。

| やってよい | やってはいけない |
|---|---|
| `source/`（保護 dir）を読む | 保護ディレクトリに書く・消す・動かす（例外: `make_fixture.py`） |
| `working/extracts/` にコピーを作る | 正本を「整理」する |
| `tools/` を改定して再実行する | `working/_*.py` を増やし続ける |
| 証拠つきでレポートを書く | Caption や推測だけで遷移・役割を断定する |
| inventory を構成の正にする | 正規表現で callgraph を自動生成する |

モットー: **自問自答 + 自己改善**  
サイクル: **検証 → 理解 →（任意）実装**

---

## 1. 起動手順（毎回）

1. `AGENTS.md` を Read（入口・正典層）
2. 本ファイルを Read（今ここ）
3. 対象アプリがあるなら消費者の `docs/ai-dev-context.md` を Read（無ければ `docs/templates/ai-dev-context.md` から作る提案のみ）
4. キット自体を直すときだけ `docs/kit-dev-context.md` を Read
5. `docs/flow/_master.md` でフェーズと不変条件を確認
6. 作業種別に応じて skill / command を Read してから実行

起動順の正: **AGENTS.md → 本ファイル**（QUICKREF / sessionStart も同じ）。  
hooks の `sessionStart` が短いリマインダを出すことがある。それは補助であり、本ファイルの代替ではない。

---

## 2. ディレクトリ契約

```
source/                 # 正本（読取専用）— archaeology.config.json で別名可
working/extracts/<stem>/
working/reports/
working/skeletons/
tools/                  # 解析の正。足りなければここを直す
docs/
.cursor/
```

- **正本** = ユーザーが渡した VB6 ツリー。改変禁止
- **抽出** = 分析用コピー。編集してよいが本番へ戻さない
- **レポート** = 人間と AI の共有メモリ。事実と推定を混ぜない

保護ディレクトリ名の一覧は `archaeology.config.json` の `protected_source_dirs`。  
hooks（`.cursor/hooks/`）が書込ツールと破壊的 shell を阻む。

---

## 3. エンコーディング

- VB6 ソースは **CP932** 前提（`tools/lib/config.py`）
- Cursor の `Read` で日本語が化けても、**化けた文字を引用根拠にしない**
- 内容判断・行番号引用は Python ツール出力または `decode('cp932')` 経由

---

## 4. 標準パイプライン

```text
[正本 .vbp]
    → extract_vbp.py          → working/extracts/<stem>/
    → vb6_inventory.py        → working/reports/<stem>_inventory.{json,md,html}
    → verify_inventory.py     → mismatches: none
    → frm_deep_read.py        → *_deep_read.md + skeletons
    → runtime_layout.py       → runtime_layout.md + runtime-layout.json
    → comprehension ticks     → <stem>_comprehension.html（人手+証拠）
```

各ステップの詳細は `docs/workflow.md`。  
コマンド入口は `.cursor/commands/`。

---

## 5. 事実 vs 推定（絶対）

| 種別 | 定義 | 置き場 |
|---|---|---|
| 事実 | ソースから機械的または精読で確定（定義・行範囲・パス文字列） | inventory / schema / 精読メモの「事実」節 |
| 推定 | 役割・業務意味・「たぶんこう動く」 | 証拠（ファイル / Sub / 行 or 引用）必須 |

- inventory に無いファイル名・Sub 名をレポートに書かない
- 呼び出し関係は **読んだ Sub の分だけ**
- 「100%」はチェックリスト達成率。アプリ全体の完全理解を意味しない

方法論の正: `.cursor/rules/vb6-analysis.mdc` · `docs/methodology.md`

---

## 6. ツール改定ルール

1. 抽出が足りない・誤検知 → **ワンショットを増やさず** `tools/` を直す
2. 直したら影響レポート / skeleton を再生成する
3. `tools/README.md` を更新する
4. 一時検証だけ `working/_verify_*.py` を使ってよい（確認後削除）。定型検証は `tools/verify_inventory.py`

---

## 7. やってはいけないアンチパターン

1. Caption「検索」だけで画面遷移を実装する（メニューが死んでいることがある）
2. Invisible / 到達不能 Form を必須機能として実装する
3. 完了宣言を信用して再監査しない
4. PowerShell `Set-Content` / `-replace` で日本語リテラルを含むファイルを壊す
5. 正本パスを「便利だから」書き換えて保存する
6. 旧 callgraph 自動推定を復活させる

---

## 8. 消費者リポとの関係

このキット単体でも調査できる。  
アプリ再実装リポに入れる場合:

- キット = 方法論 + 汎用 tools + .cursor
- 消費者 = `docs/ai-dev-context.md`（現状）+ アプリ固有 tools + `working/web/` 等

採用手順: `docs/adopting-in-a-project.md`  
テンプレ: `docs/templates/`

---

## 9. 自己点検

キットが健全か確認するとき:

```powershell
python tools/make_fixture.py
python tools/extract_vbp.py "source\mini_vbp\mini_vbp.vbp"
python tools/vb6_inventory.py working\extracts\mini_vbp
python tools/verify_inventory.py
python tools/frm_deep_read.py Form1.frm --extract working\extracts\mini_vbp
python tools/runtime_layout.py --extract working\extracts\mini_vbp
```

または `/kit-smoke`。

---

## 10. 応答方針（ユーザー向け）

- 日本語で簡潔に
- 長い現状一覧を `AGENTS.md` に複製しない（`ai-dev-context` へ）
- 提案→確認→実行がユーザー方針のときは、破壊的変更の前に一度止める
- 「続けて」「進めて」は調査パイプラインの次ステップを実行してよい（ユーザーが止めと明示するまで）
