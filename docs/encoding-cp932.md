# エンコーディング（CP932）

## 事実

- 日本語 VB6 の `.vbp` / `.frm` / `.bas` / `.cls` は多くの場合 **Windows CP932**
- UTF-8 として読むと日本語が壊れる
- Cursor のファイル Read も日本語を化かすことがある

## エージェント規則

1. ソース内容の判断は `tools/`（`decode_vb6_bytes`）経由の出力を正とする
2. 化けた文字列をレポートに「原文引用」として載せない
3. レポート成果物（MD/JSON/HTML）は **UTF-8** で書いてよい
4. PowerShell の `Set-Content` / `-replace` で `.tsx` や日本語リテラルを含むファイルを書き換えない（破壊例あり）
5. PowerShell の二重引用符文字列内では `` ` `` がエスケープになる。`` `F ``→FF（`\x0c`）、`` `v ``→VT（`\x0b`）などで Markdown のインラインコードが壊れる。検出: `python -m tools scan-chars`（hits=0）

行番号つきで CP932 ソースを見るときは `python -m tools lines <file> <start>-<end>`。

## 設定

`archaeology.config.json`:

```json
{
  "encoding": "cp932",
  "encoding_fallbacks": ["utf-8-sig", "utf-8"]
}
```

フォールバックは「読めなかったとき」用。成功したエンコーディングをレポートに残すとよい（将来拡張）。
