#!/usr/bin/env python3
"""Create a tiny CP932 VB6-like fixture under source/mini_vbp/ for smoke tests."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "source" / "mini_vbp"


VBP = """\
Type=Exe
Form=Form1.frm
Module=Module1; Module1.bas
Startup="Form1"
Title="ミニ考古"
ExeName32="mini.exe"
Name="mini_vbp"
"""

FRM = """\
VERSION 5.00
Begin VB.Form Form1
   Caption         =   "ミニ画面"
   ClientHeight    =   3000
   ClientWidth     =   4800
   Height          =   3405
   Left            =   120
   Top             =   120
   Width           =   4920
   Begin VB.CommandButton Command1
      Caption         =   "確定"
      Height          =   495
      Left            =   1680
      TabIndex        =   0
      Top             =   1200
      Width           =   1215
   End
   Begin VB.Label Label1
      Caption         =   "こんにちは"
      Height          =   255
      Left            =   240
      TabIndex        =   1
      Top             =   240
      Width           =   2000
   End
End
Attribute VB_Name = "Form1"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Explicit

Private Sub Form_Load()
    Me.Left = 0
    Me.Top = 0
    Label1.Caption = "読込済"
End Sub

Private Sub Command1_Click()
    Unload Me
End Sub
"""

BAS = """\
Attribute VB_Name = "Module1"
Option Explicit

Public Function AddOne(ByVal n As Long) As Long
    AddOne = n + 1
End Function
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mini_vbp.vbp").write_bytes(VBP.encode("cp932"))
    (OUT / "Form1.frm").write_bytes(FRM.encode("cp932"))
    (OUT / "Module1.bas").write_bytes(BAS.encode("cp932"))
    readme = REPO / "source" / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# source/ — protected VB6 originals\n\n"
            "Put immutable `.vbp` trees here. Hooks deny writes into this directory.\n"
            "Fixture `mini_vbp/` is for kit smoke tests only.\n",
            encoding="utf-8",
        )
    print(f"fixture written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
