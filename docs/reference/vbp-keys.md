# VBP から拾うキー

`tools/extract_vbp.py` がコピー対象とするキー:

| キー | 例 |
|---|---|
| `Form=` | `Form=Form1.frm` |
| `Module=` | `Module=Module1; Module1.bas` |
| `Class=` | `Class=Class1; Class1.cls` |
| `UserControl=` | … |
| `PropertyPage=` | … |
| `UserDocument=` | … |
| `Designer=` | … |
| `RelatedDoc=` | … |
| `ResFile32=` | … |

## スキップ（正常）

| キー | 理由 |
|---|---|
| `Reference=` | COM/TLB。ファイルコピー対象外。`skipped_ref` に件数記録 |

## inventory が読むキー

`tools/vb6_inventory.py` の事実層（`VBP_META_CANON` ほか）。白リスト外のキーは無視する。

| 種別 | キー |
|---|---|
| ファイル一覧 | `Form=` · `Module=`（`Ident; path`）· `Class=`（同形） |
| コンポーネント | `Object=`（OCX 等。`;` 後のファイル名、無ければ `file: null` + `raw`） |
| メタ | `Startup=` · `Title=` · `ExeName32=` · `IconForm=` · `Name=` · `Command32=` · `HelpFile=` · `MajorVer=` · `MinorVer=` · `RevisionVer=` · `VersionComments=` · `VersionCompanyName=` · `VersionFileDescription=` · `VersionLegalCopyright=` · `VersionProductName=` |

パス欠落（`Module=Foo` / 空の `Form=` 等）は一覧に入れず `warnings` に記録する。  
`--skip-parent-common` 時、`..\..\` 系パスは `skipped_parent_common` に回す（既定オフ）。

## 同伴ファイル

`.frm` と同名の `.frx` があれば抽出時に同伴コピーする。
