# Encoding (CP932)

**[English](encoding-cp932.md)** · **[日本語](../encoding-cp932.md)**

## Facts

- Japanese VB6 `.vbp` / `.frm` / `.bas` / `.cls` is usually **Windows CP932** (a Shift-JIS variant), not UTF-8
- Reading as UTF-8 garbles Japanese captions and string literals
- Cursor’s file Read can mojibake the same bytes

## Agent rules

1. Treat tool output (`tools/`, `decode_vb6_bytes`) as the source of truth for file contents
2. Do not paste garbled text into a report as a “quote”
3. Generated reports (MD / JSON / HTML) may be UTF-8
4. Do not rewrite Japanese literals with PowerShell `Set-Content` / `-replace`
5. Inside PowerShell double-quoted strings, `` ` `` is an escape. `` `F `` becomes FF (`\x0c`), `` `v `` becomes VT (`\x0b`), which breaks Markdown inline code. Detect with `python -m tools scan-chars` (expect `hits=0`)

Line-numbered CP932 views: `python -m tools lines <file> <start>-<end>`.  
Full-file Cursor Read: `python -m tools readable` writes `working/readable/<stem>/` (same physical lines). Inventory and citations still use the extract.

## Console output

Decode can succeed and then **print** can fail: a Japanese Caption on an English-locale Windows console (cp1252) raises `UnicodeEncodeError`. Each tool calls `enable_utf8_stdio()` from `lib/console.py` at the start of `main()`. New tools need the same one-liner. Regression: `tools/test_console.py` with `PYTHONIOENCODING=cp1252`.

## Config

`archaeology.config.json`:

```json
{
  "encoding": "cp932",
  "encoding_fallbacks": ["utf-8-sig", "utf-8"]
}
```

Fallbacks are for “could not decode”. Recording which encoding succeeded is useful later; the kit does not invent a business meaning from that.
