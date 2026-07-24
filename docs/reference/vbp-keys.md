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

## メタ（inventory が読む）

`Startup=` · `Title=` · `ExeName32=` · `IconForm=` · `Name=`

## 同伴ファイル

`.frm` と同名の `.frx` があれば抽出時に同伴コピーする。
