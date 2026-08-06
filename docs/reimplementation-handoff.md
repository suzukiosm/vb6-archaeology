# 再実装ハンドオフ・チェックリスト（製品面）

調査 OS（inventory / deep-read / layout / comprehend）の **「調査完了」** と、再実装の **「製品 UI 完了」** は別物である。  
本チェックリストは境界の漏れ防止用。キットに Next.js やデザインシステムは載せない。

前提: 再実装 UI は **「VB 見た目の複製」ではなく「VB 操作契約の複製」**。  
Caption / デザイナ座標の直写しと、オペレータ向け製品文言は分離する。

---

## 1. 製品面チェックリスト（出荷前）

実装に入る前・画面を製品扱いにする前に確認する。未確認は「未確認」と残す。

- [ ] **オペレータ向け文言** — VB の Caption / MsgBox / デバッグ用ラベルをそのまま製品面に出していないか
- [ ] **非表示メニュー** — デザイナ `Visible = False`（および実行時に隠れる経路）の項目を製品 UI に出していないか
- [ ] **子 Form の見せ方** — 呼び出し元の上に重ねるか、戻る導線が二重になっていないか（下節の Show パターン）
- [ ] **読込中表示は 1 箇所** — meta / spinner / status の三重表示を避けているか
- [ ] **空状態** — 表内メッセージに集約し、err 帯と二重にしていないか
- [ ] **拠点名・内部コード** — 調査メモ用の拠点名や内部 ID が製品ラベルに残っていないか
- [ ] **VB 証跡の隔離** — 開発者向け証跡（ソース行・Form 名の直出し等）は Dev 面のみか

tick 単位のメモ欄: comprehension の任意節 **`product_ui_notes`**（[`templates/comprehension-tick.md`](templates/comprehension-tick.md)）。

---

## 2. Show パターン（再実装の安定化）

VB の `Show` / `Load` / MDI 子は、Web では取り違えやすい。  
**調査完了後・配線前**に、Form ごとに次の候補を 1 つ選ぶ（断定できないときは根拠と「未確認」を残す）。

| `show_style` | 意味 | Web 側の典型 |
|---|---|---|
| `mdi_child` | MDI 子として常駐・メニューから置換 | シェル内コンテンツ入替（呼び出し元シェルは残す） |
| `modal_overlay` | モーダル重ね（選択・カレンダー・プリンタ・確認） | ダイアログ / ドロワ。呼び出し元は背面に残す |
| `navigate` | 別画面遷移でよい（印刷プレビュー等） | フルページ遷移 + 明確な戻る |

### ヒューリスティック（証拠の置き場）

`python -m tools deep-read` と `python -m tools inventory` が Form 自身の `MDIChild` と
`Foo.Show [vbModal|…]` から **候補**を出す（inventory=全文面、deep-read=ライブ Sub 優先）。  
横断一覧は `python -m tools excerpt` または `serve` の `/excerpt`。

| 痕跡（例） | 寄せる候補 |
|---|---|
| `Form.Show vbModal` / `Show 1` | `modal_overlay` |
| デザイナ `MDIChild = -1` | `mdi_child`（**その Form 自身**） |
| 印刷プレビュー等で呼び出し元を隠してもよいと合意 | `navigate`（合意のみ・機械では出さない） |
| 素の `.Show` / `vbModeless` | `unknown`（証拠だけ残す） |
| `Load` のみで直後に非表示メンテ | 製品面に出さない／Dev のみ（必須 UI にしない） |

**失敗パターン（実戦）:** モーダル相当をフルページ遷移にし、呼び出し元が消える。  
`modal_overlay` と判定した Form は、呼び出し元を残す実装を選ぶ。

frm-audit を使う場合は「到達可否」表に `show_style` 列または備考を足してよい（[`templates/frm-audit.md`](templates/frm-audit.md)）。

---

## 3. 調査完了 ≠ 製品 UI 完了

| 完了の種類 | 満たすもの | 満たさないもの |
|---|---|---|
| 調査（キット） | inventory 正・tick 証拠・layout 参照 | 製品文言・遷移 UX・本番データ安全 |
| 製品 UI（消費者） | 上表チェックリスト + 操作契約 | 「tick が厚い」だけでは不足 |

comprehend の Stop（チェックリスト達成・ユーザー「止め」・証拠不足）と、製品面の Stop は別。対応は [`templates/CURRENT.md`](templates/CURRENT.md)。

---

## 4. 関連

- 採用・データ書込抑止: [`adopting-in-a-project.md`](adopting-in-a-project.md)
- 長セッション正本: [`templates/CURRENT.md`](templates/CURRENT.md)
- ワークフロー Step 8: [`workflow.md`](workflow.md)
