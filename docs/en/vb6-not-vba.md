# VB6 is not VBA

**[English](vb6-not-vba.md)** · **[日本語](../vb6-not-vba.md)**

GitHub’s language bar and search often treat `.bas` / `.cls` / `.frm` as VBA. This kit’s subject is **Visual Basic 6.0 (desktop)**.

## Contrast (facts)

| | Visual Basic 6 (VB6) | VBA | VB.NET | VBScript |
|---|---|---|---|---|
| What | Desktop IDE / runtime (roughly 1998–2008) | Macros hosted in Office (Excel, …) | A .NET language | Windows scripting |
| Project | `.vbp` (this kit’s entry) | `.xlsm` / host documents | `.vbproj` | `.vbs` |
| UI | `.frm` plus companion `.frx` | UserForm (different format) | WinForms / WPF / … | None |
| This kit | **In scope** | Out of scope | Out of scope | Out of scope |

Rubberduck and other Office-macro tools are not this repository. VB6 parser libraries (syntax trees) are a different job. This is an investigation OS: read-only originals, CP932, facts separated from guesses.

## What this repo does about the mix-up

Fixture and extract `.bas` / `.cls` / `.frm` / `.ctl` are labeled **Visual Basic 6.0** via Linguist alias `vb6` in [`.gitattributes`](../../.gitattributes). The `vba` topic is not used.

Do not judge Japanese source from Cursor’s file Read alone. See [encoding-cp932.md](encoding-cp932.md).
