# キット改良アイデア（提案・未採用）

**これは提案。** 採用するまで実装しない（P0 · P1 · P2 · P3 は 2026-08-16 採用済）。1 テーマ 1 PR。  
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
| F1 | ~~`extract` は extra キーをコピーするが inventory は Form/Module/Class だけ~~ **採用済 2026-08-16** | `vb6_inventory.parse_vbp` · [`reference/vbp-keys.md`](reference/vbp-keys.md) |
| F2 | ~~同伴コピーは `.frm`→`.frx` のみ~~ **採用済 2026-08-16** 同 stem の既知同伴 | `extract_vbp.companion_paths` |
| F3 | `deep-read` は `.frm` 単体。`.cls` / `.bas` に同等の表面レポートが無い | `frm_deep_read` の範囲注記 · `methodology.md` |
| F4 | ~~`layout` は `.frm` + `.bas`。`.cls` は走査しない~~ **採用済 2026-08-16** | `runtime_layout.py` · `iter_module_paths` |
| F5 | 前方 GoTo 飛び越えは一般化済。~~`On Error GoTo` / `GoSub` は対象外~~ **採用済 2026-08-16**（ラベル地図）。後方 GoTo は対象外 | `frm_deep_read` · [`anti-patterns.md`](reference/anti-patterns.md) 9e |
| F6 | ~~メニューは警告のみ。木構造は skeleton の一級市民ではない~~ **採用済 2026-08-16** `menu_tree` | `analyze_menus` · `build_menu_tree` |
| F7 | ~~`serve` に目次が無い~~ **採用済 2026-08-16** `/` ランディング | `serve_reports.py` |
| F8 | ~~`smoke` の `/excerpt` live GET は意図的未実装~~ **採用済 2026-08-16** `serve --live-get` | `serve_reports.live_get` |
| F9 | ~~バージョン表示は `0.1.0` のまま。`[Unreleased]` に 0.1.0 以降の機能が厚い~~ **採用済 2026-08-16** `0.2.0` | `tools/__init__.py` · `CHANGELOG.md` · `tools/lib/version.py` |
| F10 | ~~フィクスチャに UserControl / `On Error` / `GoSub` / I/O 5 種が無い~~ **採用済 2026-08-16** `test_make_fixture.py` | `tools/make_fixture.py` |
| F11 | GitHub Issues は空。改善テンプレはあるがバックログの置き場が無い | `gh issue list` · `.github/ISSUE_TEMPLATE/feature_request.yml` |
| F12 | ~~パイプライン進捗を出すコマンドが無い~~ **採用済 2026-08-16** `python -m tools status` | `tools/status.py` |

`show_calls`（Form 単位の出方向事実）は採用済。無いのは **入方向の転置** と **進捗の機械集計**。

---

## 2. 優先提案

### P0 — 事実層の一貫性（哲学に合う・すぐ価値）

#### A. inventory が extract したファイル種を棚卸しする — **採用済 2026-08-16**

`UserControl=` / `PropertyPage=` / `UserDocument=` / `Designer=` を Form/Module/Class と同列に棚卸し（`.ctl` 等はデザイナ解析）。`RelatedDoc=` / `ResFile32=` は一覧のみ（中身は解析しない）。fixture に `MiniCtl.ctl`。PARSER_VERSION `inv-6`。

#### B. Show 逆引き（既存 `show_calls` の転置） — **採用済 2026-08-16**

inventory / excerpt に「Show 文の転置（事実）」を出す。既存 `show_calls` の逆引きのみ。ターゲットが inventory の Form（`vb_name`、なければファイル stem）に一意に無いときは `unresolved`。呼び出しグラフではない。

#### C. `python -m tools status` — **採用済 2026-08-16**

`python -m tools status`（`--json-only` 可）。extract / inventory / `<stem>_verify.json` / deep-read 数÷Form 数 / tick 数÷プロシージャ数 / excerpt / layout / io-catalog の有無を JSON + 3 行で出す。推定も次手も付けない。sessionStart が同じ 3 行を出す。複数 extract は `default_extract`（既存契約）。

---

### P1 — エージェントの次手

#### D. `comprehend --unticked` / `--suggest` — **採用済 2026-08-16**

`python -m tools comprehend --unticked`（`--json-only` 可）。`--suggest` はヒューリスティックと明記し、Startup `Form_Load`/`MDIForm_Load` → その Form の outbound `show_calls` 先の `Form_Load` → 残り公開 Sub の順。自動 tick しない。未解決 Show は載せない。空なら「未 tick 0」。

#### E. `serve` ランディング — **採用済 2026-08-16**

`/` に inventory · comprehension · excerpt · layout · deep-read へのリンク（存在する成果物のみ。無い種類は「なし」）。`/excerpt` は常に出す。`file://` 禁止は維持。ページ下部にディレクトリ生一覧。

#### F. excerpt に Module / Class 表面 — **採用済 2026-08-16**

excerpt に未 tick の `.bas`/`.cls` と `Declare` 件数の節を追加。DLL 意味は書かない。`.ctl` は含めない（P2-G の範囲）。

---

### P2 — 深読みの穴

#### G. `.cls` / `.bas` 表面レポート — **採用済 2026-08-16**

inventory ファイル節 + excerpt に `Implements` / `WithEvents` / `Instancing`（生の整数）/ `VB_Creatable`·`VB_Exposed` / 公開 Property 件数。deep-read の Form 版はコピーしない。PARSER_VERSION `inv-7`。fixture `Widget.cls` に Implements / WithEvents / Instancing / Property Get。

#### H. `On Error GoTo` / `GoSub` を候補として出す — **採用済 2026-08-16**

ラベル地図に `on_error` / `gosub`（および `gosub_conditional`）を載せる。飛び越えスパンは前方 `GoTo` のみ（エラー時だけ飛ぶ / Return で戻る）。デッド確定しない。anti-patterns 9e を更新。fixture `Command1_Click` に 1 本ずつ。

#### I. 横断 I/O カタログ — **採用済 2026-08-16**

`python -m tools io-catalog`。extract 内の `Open` / `Kill` / `Name` / `Get` / `Put` を file:line で列挙。業務意味は書かない。既存 skeleton の `goto_skipped_stmts` と file+line 突合。fixture `IoDemo` + `Form_Load` 前方 GoTo 越し `Open`。

#### J. メニュー木を skeleton へ — **採用済 2026-08-16**

skeleton `menu_tree` + deep-read「メニュー木（デザイナ値）」。親子・Caption・Visible/Enabled は Begin 値。`has_click` は `Name_Click` の有無（事実）。実行時 `Enabled =` は layout（混ぜない）。警告 `menu_warnings` は維持。fixture `mnuFile` / `mnuOpen` / `mnuHidden`。

#### K. layout が `.cls` も見る — **採用済 2026-08-16**

`.bas` と同じく `.cls` を走査（`iter_module_paths`）。VB_Name があればそれを `file_vb` にする。幾何代入は稀でも見ないことをやめる。fixture `Widget.PlaceHost` が `Form1.Left = 50`。`.ctl` は対象外。

#### L. 同伴 `.ctx` / デザイナ同伴 — **採用済 2026-08-16**

`companion_paths`: `.frm`→`.frx` · `.ctl`→`.ctx` · `.pag`→`.pgx` · `.dob`→`.dox` · `.dsr`→`.dsx`。中身は解析しない。`companion_frx` は互換（`.frx` のみ）。fixture `MiniCtl.ctx`。

---

### P3 — 検証・リリース衛生

#### M. smoke で `/excerpt` を live GET — **採用済 2026-08-16**

`python -m tools serve --live-get`。一時ポートで `/` と `/excerpt` を GET し 200 を見る。`serve --check` の次に smoke が回す。長寿命サーバは立てない。

#### N. 0.2.0 タグ — **採用済 2026-08-16**

`[0.2.0] - 2026-08-16`。`tools/__init__.py` `__version__` = `0.2.0`。`tools/lib/version.py` + `test_version.py` が CHANGELOG の最新日付見出しと一致を見る。git タグ `v0.2.0` は main 合流後。

#### O. fixture を薄く厚くする — **採用済 2026-08-16**

`make_fixture.py` に UserControl · `On Error GoTo` · 前方 GoTo · `GoSub` · I/O 5 種（P0/P2 で追加済）。`test_make_fixture.py` が temp へ書いてパーサで契約を見る（`source/` へは書かない）。アプリ意味は載せない。

#### P. inventory と deep-read の `show_style` 照合 — **採用済 2026-08-16**

`python -m tools verify-show`。同じ Form の self / 同行 Show が食い違ったら hard（exit 1）。inventory だけの Show（デッド Sub 等）と skeleton 欠は警告・exit 0。どちらが正かは決めない。fixture `Ghost_Click` が inventory_only の回帰。

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

P0 · P1 · P2 · P3 は採用済。文書化された優先提案はここまで。完全 callgraph / Next / 業種は「やらない」のまま。
