# 方法論 — 事実と推定・検証・スコア

`.cursor/rules/vb6-analysis.mdc` と同内容の人間向け正本。矛盾したら rule と本ファイルを同時に直す。

## 原則: 事実と推定を分離する

1. **事実（facts）** = ソースから機械的に確定できる情報。  
   例: プロシージャ定義と行範囲、コントロール一覧、VBP 構成、Declare。  
   → `python -m tools inventory` の `<stem>_inventory.*` が構成の正。
2. **推定（inference）** = 読解・解釈（役割ラベル、呼び出し関係、業務フロー）。  
   → 必ず証拠（ファイル名・Sub・行番号・引用）を併記。書けないなら書かない。
3. 呼び出し関係の正規表現一括推定はしない（誤エッジがノイズになる）。

## 検証を伴わないレポートは出さない

- 機械抽出は独立手段でクロスチェックする  
  例: プロシージャ数 == 行頭 `End Sub|Function|Property` 数（`python -m tools verify`）
- 既存レポートを引用する前に inventory と矛盾しないか確認
- 再利用解析は `tools/` に置き、サイクル中に改定する

## 検証 → 理解 → 実装

1. **検証** — レポート / skeleton / 再実装を `working/extracts/` に突き合わせる  
2. **理解** — `tools/` を先に使う。不足ならツール改定→再実行→証拠更新  
3. **実装** — 確定事実のみ再実装側へ。推測で UI・イベントを埋めない

## 読取・出力の約束

- エンコーディング: CP932（設定可）
- 正本ディレクトリ: 読取専用（hooks）
- 成果: `working/reports/` に JSON + MD + 必要なら HTML
- HTML 閲覧: ローカル HTTP（`file://` 不可）

## 理解度スコア

- スコアはチェックリスト達成率。チェックリスト自体を成果物内に明記する
- 100% = そのチェックリストの全項目に証拠がある、という意味のみ
- 「アプリを完全に理解した」とは書かない

## Form 深読みの範囲

- `frm_deep_read.py` は **対象 .frm 単体**の解析。他 .frm/.bas からの参照（`Show` 呼び元・外部操作）は見えない
- イベント数 0 を「孤立・到達不能」と即断しない
- 親が `VB.Frame` / `VB.PictureBox` で設計時 `Visible=0` かつコード非参照（dead container）のとき、子孫に `ancestor_hidden` / `ancestor_hidden_by` が付く（実行時非表示相当）

## 再実装消費者向け（任意・1段落）

意図的未移植（外部 EXE・実機連携等）と取りこぼしを監査で区別する。  
.frm 再監査の型: `docs/templates/frm-audit.md`（採用手順は `docs/adopting-in-a-project.md`）。  
詳細の実装・棚卸し表は消費者リポ側。キットは証拠抽出まで。

## レポートの正（canon）

| 対象 | 正 | 手段 |
|---|---|---|
| 構成 | `<stem>_inventory.*` | `vb6_inventory.py` |
| 抽出 | `working/extracts/<stem>/` | `extract_vbp.py` |
| Form 深読み | `*_deep_read.md` + skeleton | `frm_deep_read.py` |
| 実行時座標 | `runtime_layout.*` | `runtime_layout.py` |
| ツール索引 | `tools/README.md` | 人手 |
| セッション現状（消費者） | `docs/ai-dev-context.md` | 人手 |
| キット保守 | `docs/kit-dev-context.md` | 人手 |
| フロー | `docs/flow/_master.md` | 人手 |
