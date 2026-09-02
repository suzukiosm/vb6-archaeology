# VB6 is not VBA

**[English](en/vb6-not-vba.md)** · **[日本語](vb6-not-vba.md)**

GitHub の言語バーや検索は `.bas` / `.cls` / `.frm` を VBA と誤ることがある。本キットの対象は **Visual Basic 6.0（デスクトップ）** である。

## 対比（事実）

| | Visual Basic 6 (VB6) | VBA | VB.NET | VBScript |
|---|---|---|---|---|
| 何か | 1998–2008 頃のデスクトップ IDE / ランタイム | Office（Excel 等）に載るマクロ言語 | .NET 上の言語 | Windows スクリプト |
| プロジェクト | `.vbp`（本キットの入口） | `.xlsm` / ホスト文書 | `.vbproj` | `.vbs` |
| 画面 | `.frm` + 同伴 `.frx` | UserForm（別形式） | WinForms / WPF 等 | なし |
| 本キット | **対象** | 対象外 | 対象外 | 対象外 |

VBA 向けの Rubberduck や Office マクロ解析は、このリポの範囲ではない。VB6 のパーサライブラリ（構文木）とも役割が違う。調査 OS（読取専用・CP932・事実と推定の分離）である。

## このリポでやっていること

フィクスチャと抽出対象の `.bas` / `.cls` / `.frm` / `.ctl` は GitHub Linguist の別名 `vb6`（Visual Basic 6.0）で明示する（[`.gitattributes`](../.gitattributes)）。VBA トピックは付けない。

日本語ソースを Cursor の Read だけで判断しない。 [encoding-cp932.md](encoding-cp932.md)。
