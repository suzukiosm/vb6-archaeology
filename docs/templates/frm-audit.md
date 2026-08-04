# 〈Form〉（〈file.frm〉）再監査

- 日付: 〈YYYY-MM-DD〉
- 抽出: `working/extracts/〈stem〉/`
- inventory: `working/reports/〈stem〉_inventory.*`（名前・プロシージャの正）
- deep-read: `working/reports/〈name〉_deep_read.md` · skeleton: `working/skeletons/〈name〉-skeleton.json`
- 実行時座標: `working/reports/runtime_layout.md`（開時コード座標・`codeControlMoves`）
- 本ファイルの置き場（消費者）: `working/reports/audit/〈name〉_frm_audit.md`

事実と推定を混ぜない。推定は「推定:」ラベル + 証拠（ファイル / Sub / 行）。

---

## 1. 到達可否

| 項目 | 結果 | 証拠 |
|---|---|---|
| UI から開けるか | 到達可 / 不能 / 未確認 | 〈Show・メニュー Enabled・親 Visible 等〉 |
| イベント 0 の扱い | 即断しない（.frm 単体解析の限界） | deep-read 注記 / 他 Form からの操作 |
| `ancestor_hidden` | 有 / 無 | skeleton または deep-read |

到達不能なら必須機能として実装しない（Dev 検証用と明記するか除外）。

---

## 2. 再監査順（固定3段）

この順以外で「完了」としない。

### (1) VB6 読解誤り

- Caption だけで遷移・役割を断定していないか
- Invisible / Disabled / Click 無しメニューを現役扱いしていないか
- inventory に無いファイル名・Sub 名を書いていないか
- デッドコンテナ配下（`ancestor_hidden`）を必須 UI にしていないか

| 所見 | 種別 | 証拠 |
|---|---|---|
| 〈…〉 | 事実 / 推定 | 〈…〉 |

### (2) UI 位置

ずれ・見た目微調整は **保留可**（消費者側のレイアウト棚卸しへ）。  
ただし次は **監査対象**（保留にしない）:

- 開時のコード部座標（`Form_Load` / Show 近傍の Left/Top/Width/Height）
- 親 Frame / PictureBox によるクリップ
- 背面完全被覆（実行時に見えない＝VB6 非表示相当）
- `runtime_layout` の `codeControlMoves`

| 対象 | 設計時 / 実行時 | 再実装側 | 判定 | 証拠 |
|---|---|---|---|---|
| 〈Ctrl〉 | 〈…〉 | 〈有/無/ずれ〉 | OK / 要対応 / 保留 | 〈…〉 |

### (3) 機能取りこぼし（実行経路）

実行され得る Click / Change / Load / タイマー等で、再実装側に対応が無いもの。

| 経路（Sub） | VB6 行為（要約） | 再実装 | 判定 | 証拠 |
|---|---|---|---|---|
| 〈Sub〉 | 〈…〉 | 有 / 無 / 部分 | 取りこぼし / 意図的未移植 / OK | 〈…〉 |

---

## 3. 意図的未移植 vs 取りこぼし

| 区分 | 定義 | 扱い |
|---|---|---|
| 意図的未移植 | スコープ外と合意した外部連携・実機依存など（例: 外部 EXE 起動、実 FAX / 実プリンタ経路） | 表に残し、再実装しない旨と根拠を書く |
| 取りこぼし | 実行経路上あるのに再実装・配線が無い | 次候補へ。証拠必須 |

混同しない。キャプションや「あったほうがよい」だけでは取りこぼしにしない。

### 意図的未移植（本 Form）

| 項目 | 根拠 |
|---|---|
| 〈なし / 項目〉 | 〈合意・スコープ文書・ソース行〉 |

### 取りこぼし（本 Form）

| 項目 | 証拠 | 次アクション |
|---|---|---|
| 〈…〉 | 〈…〉 | 〈…〉 |

---

## 4. イベント表（ライブ中心）

deep-read / inventory と突合。死んだプロシージャは「デッド」と明記。

| Sub | 行 | 役割（推定はラベル） | 再実装 | 備考 |
|---|---|---|---|---|
| 〈…〉 | L… | 〈事実 / 推定: …〉 | 〈…〉 | 〈…〉 |

---

## 5. 次候補（1〜3 件）

証拠つき。優先は再監査順 (1)→(3)。

1. 〈…〉 — 証拠: 〈…〉
2. …
3. …

---

## 6. 参照（機械出力）

- inventory 照合: `python -m tools verify` → `python -m tools verify-names`
- 深読み再生成: `python -m tools deep-read 〈file.frm〉 --extract working/extracts/〈stem〉`
- 行引用: `python -m tools lines working/extracts/〈stem〉/〈file.frm〉 〈start〉-〈end〉`
