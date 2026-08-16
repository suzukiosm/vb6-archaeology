# キット改良アイデア（提案・未採用）

**これは提案。** 採用するまで実装しない（P0-C `status` は 2026-08-16 採用済）。1 テーマ 1 PR。  
消費者アプリのセッション事実ではない。キット保守用。現状の正は [`kit-dev-context.md`](kit-dev-context.md)。

方針は変えない: 事実と推定を混ぜない · 正規表現一括の callgraph は作らない · 標準ライブラリのみ · アプリ固有は消費者へ。

---

## 0. やらない（既存方針の再確認）

| 対象 | 理由 |
|---|---|
| inventory 横断の「誰が誰を Show するか」完全グラフ | `CHANGELOG` Deferred。呼び出し推定になる |
| Next.js / CSS / 業種ドメインの同梱 | キットは証拠・名前・保護・手順に留める |
| コメント仕様書化 | vbSpec 由来でも非採用 |
| 伝票 DAT · 特定 Form · 実機連携 | DO NOT PORT |

**許容する中間:** すでに集めた事実の転置・集計（推定エッジを増やさない）。

---

## 1. 今ある穴（事実）

コードと文書から機械的に確認できる不一致。ここが提案の根拠。

| # | 穴 | 根拠 |
|---|---|---|
| F1 | `extract` は `UserControl` / `PropertyPage` / `UserDocument` / `Designer` / `RelatedDoc` / `ResFile32` をコピーするが、`inventory` は `Form` / `Module` / `Class` しか棚卸ししない | `extract_vbp.FILE_KEYS` vs `vb6_inventory.parse_vbp` · [`reference/vbp-keys.md`](reference/vbp-keys.md) |
| F2 | 同伴コピーは `.frm`→`.frx` のみ。`.ctl` の `.ctx` 等は見ない | `extract_vbp.companion_frx` |
| F3 | `deep-read` は `.frm` 単体。`.cls` / `.bas` に同等の表面レポートが無い | `frm_deep_read` の範囲注記 · `methodology.md` |
| F4 | `layout` は `.frm` + `.bas`。`.cls` は走査しない | `runtime_layout.py` 末尾の glob |
| F5 | 前方 GoTo 飛び越えは一般化済。`On Error GoTo` / 後方 GoTo / `GoSub` は対象外 | `frm_deep_read` · [`anti-patterns.md`](reference/anti-patterns.md) 9e |
| F6 | メニューは「死んでる / Click 無し」警告のみ。木構造（親子・Enabled/Visible）は skeleton の一級市民ではない | `analyze_menus` |
| F7 | `serve` に目次が無い。ディレクトリ一覧 + `/excerpt` だけ | `serve_reports.py` |
| F8 | `smoke` の `/excerpt` live GET は意図的未実装 | `CHANGELOG` Deferred |
| F9 | バージョン表示は `0.1.0` のまま。`[Unreleased]` に 0.1.0 以降の機能が厚い | `tools/__init__.py` · `CHANGELOG.md` |
| F10 | フィクスチャに UserControl / `On Error` / `GoSub` が無い | `source/mini_vbp/`（Form · Module · Class のみ） |
| F11 | GitHub Issues は空。改善テンプレはあるがバックログの置き場が無い | `gh issue list` · `.github/ISSUE_TEMPLATE/feature_request.yml` |
| F12 | ~~パイプライン進捗を出すコマンドが無い~~ **採用済 2026-08-16** `python -m tools status` | `tools/status.py` |

`show_calls`（Form 単位の出方向事実）は採用済。無いのは **入方向の転置** と **進捗の機械集計**。

---

## 2. 優先提案

### P0 — 事実層の一貫性（哲学に合う・すぐ価値）

#### A. inventory が extract したファイル種を棚卸しする

`UserControl=` 等を `forms` / `modules` / `classes` と同型の一覧にする（Ident; path、パス欠落は `warnings`）。プロシージャ抽出は既存の `.frm`/`.bas`/`.cls` パーサを拡張するか、まず **ファイル一覧だけ** でも穴 F1 は塞がる。

- やらない: OCX の中身解析、`.res` バイナリの意味付け
- 検証: `PARSER_VERSION` を上げる · fixture にダミー `.ctl` を 1 つ

#### B. Show 逆引き（既存 `show_calls` の転置）

各 Form の outbound を集計し、「この Form を Show しているファイル・行」を出す。**新しい呼び出しを推定しない。** 文字列ターゲットが inventory に無いときは `unresolved` と残す（エッジを作らない）。

置き場の候補: inventory HTML の既存 Show 表の隣、または `excerpt`。  
「完全グラフ」とは呼ばない。キャプションは「Show 文の転置（事実）」。

#### C. `python -m tools status` — **採用済 2026-08-16**

`python -m tools status`（`--json-only` 可）。extract / inventory / `<stem>_verify.json` / deep-read 数÷Form 数 / tick 数÷プロシージャ数 / excerpt / layout の有無を JSON + 3 行で出す。推定も次手も付けない。sessionStart が同じ 3 行を出す。複数 extract は `default_extract`（既存契約）。

---

### P1 — エージェントの次手

#### D. `comprehend --unticked` / `--suggest`

excerpt が既に持つ「未 tick」を CLI でも出す。`--suggest` は **ヒューリスティックと明記**し、次の順で候補を並べるだけ（自動 tick しない）:

1. VBP `Startup=` の Form の `Form_Load` / `MDIForm_Load`
2. その Form の outbound `show_calls` 先の `Form_Load`
3. 未 tick のままの公開 Sub（inventory の手続き一覧）

層や業務意味は付けない。候補が空なら「未 tick 0」だけ。

#### E. `serve` ランディング

`/` に inventory · comprehension · excerpt · layout · deep-read へのリンクを出す。`file://` 禁止は維持。ディレクトリ生一覧は残してよい。

#### F. excerpt に Module / Class 表面

Form 中心の抜粋に、未 tick の `.bas`/`.cls` と `Declare` 件数を足す。再実装で「画面以外の入口」を見落とすのを防ぐ。

---

### P2 — 深読みの穴

#### G. `.cls` / `.bas` 表面レポート

事実のみ: `Implements` / `WithEvents` / `Instancing` / 公開 Property。deep-read の Form 版をコピーせず、短い `surface` コマンド（または inventory のファイル節拡張）にする。

#### H. `On Error GoTo` / `GoSub` を候補として出す

前方 GoTo と同型。ラベル地図に載せる。デッド確定しない。anti-patterns 9e の「未対応と知る」を「候補として見る」に進める。

#### I. 横断 I/O カタログ

extract 内の `Open` / `Kill` / `Name` / `Get` / `Put` を file:line で列挙。業務意味は書かない。GoTo 飛び越え I/O と突合できる。

#### J. メニュー木を skeleton へ

`analyze_menus` の警告に加え、親子・Caption・Visible/Enabled（デザイナ値）を JSON に出す。実行時の `Enabled =` は layout 側の既存走査と並べて読む（混ぜない）。

#### K. layout が `.cls` も見る

F4 の対称。幾何代入は稀でも、見ないことをやめる。

#### L. 同伴 `.ctx` / デザイナ同伴

`companion_frx` を「同 stem の既知同伴拡張子」に一般化。中身は解析しない（コピー漏れ防止）。

---

### P3 — 検証・リリース衛生

#### M. smoke で `/excerpt` を live GET

`CHANGELOG` Deferred の消化。`serve --check` の次に、一時ポートへ GET して 200 を見る（unittest でも可）。

#### N. 0.2.0 タグ

`[Unreleased]` の handoff / show_style / GoTo 一般化 / `mdi_chrome` / excerpt を版にする。`__version__` と `CHANGELOG` を一致させる（既存契約）。

#### O. fixture を薄く厚くする

UserControl 1 つ · `On Error GoTo` 1 本 · 前方 GoTo 既存に加えて `GoSub` 1 本。アプリ意味は載せない。P0/P2 の回帰土台。

#### P. inventory と deep-read の `show_style` 照合

同じ Form で食い違ったら警告（どちらが正かは決めない。範囲が違う: inventory=全文、deep-read=ライブ Sub 優先）。`verify` / `verify-names` に次ぐ第 3 レーンにするなら、名前は `verify-show` など別コマンド。

---

## 3. 後回しでよい

| 案 | 理由 |
|---|---|
| `.vbg` グループプロジェクト | 実戦需要が文書に無い |
| `.frx` バイナリ中身（アイコン等） | 標準ライブラリだけで意味付けしにくい。コピー済みで足りることが多い |
| 複数 VBP の横断 inventory | `default_extract` で足りる構成が既定 |
| 文書の大幅削減 | 起動順は既に短い。削減は別テーマ |
| extract 同士の diff（版考古学） | 需要が出てから |

---

## 4. 採用の進め方

1. この文書の **1 行**（例: 「P0-C status」）を指示する
2. 実装 PR はツール改定と文書同期を同じテーマに閉じる
3. 採用したら [`kit-dev-context.md`](kit-dev-context.md) の「次手」に「採用済」と日付を足し、本ファイルの該当節を短くする
4. 捨てる案は「やらない」表へ移す（消して忘れない）

P0-C は採用済。次の 1 本の候補: **P0-B Show 転置**（既に持っている `show_calls` だけ使う）。
