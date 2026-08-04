#!/usr/bin/env python3
"""Create a tiny CP932 VB6-like fixture under source/mini_vbp/ for smoke tests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.console import enable_utf8_stdio  # noqa: E402

OUT = REPO / "source" / "mini_vbp"


VBP = """\
Type=Exe
Form=Form1.frm
Form=BackupDay.frm
Module=Module1; Module1.bas
Class=Widget; Widget.cls
Object={F9043C88-F6F2-101A-A3C9-08002B2F49FB}#1.2#0; ComDlg32.OCX
Startup="Form1"
Title="ミニ考古"
ExeName32="mini.exe"
Name="mini_vbp"
MajorVer=1
MinorVer=0
RevisionVer=0
Command32=""
"""

# Filename stem (BackupDay) ≠ VB_Name (Form12) — deep_read out_key 回帰用
FRM_ALIAS = """\
VERSION 5.00
Begin VB.Form Form12
   Caption         =   "別名画面"
   ClientHeight    =   2000
   ClientWidth     =   3000
   Height          =   2400
   Left            =   120
   Top             =   120
   Width           =   3120
   Begin VB.CommandButton Command1
      Caption         =   "閉じる"
      Height          =   375
      Left            =   840
      TabIndex        =   0
      Top             =   720
      Width           =   1215
   End
End
Attribute VB_Name = "Form12"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Explicit

Private Sub Form_Load()
    Me.Left = 100
End Sub

Private Sub Command1_Click()
    Unload Me
End Sub
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
   Begin VB.Frame FrameDead
      Caption         =   "隠れた枠"
      Height          =   975
      Left            =   240
      TabIndex        =   2
      Top             =   1800
      Visible         =   0   'False
      Width           =   2000
      Begin VB.Label LabelHidden
         Caption         =   "親非表示"
         Height          =   255
         Left            =   120
         TabIndex        =   3
         Top             =   360
         Width           =   1500
      End
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

Public Const MaxRows = 100

Public Enum Mode
    ModeRead = 0
    ModeWrite = 1
End Enum

Public Type Point
    X As Long
    Y As Long
End Type

Public Declare Function GetTickCount Lib "kernel32" _
    () As Long

Public Function AddOne(ByVal n As Long) As Long
    AddOne = n + 1
End Function
"""

CLS = """\
VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "Widget"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

Public Function Ping(ByVal x As Long) As Long
    Ping = x
End Function
"""


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    argparse.ArgumentParser(
        description="Write the CP932 smoke fixture under source/mini_vbp/"
    ).parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mini_vbp.vbp").write_bytes(VBP.encode("cp932"))
    (OUT / "Form1.frm").write_bytes(FRM.encode("cp932"))
    (OUT / "BackupDay.frm").write_bytes(FRM_ALIAS.encode("cp932"))
    (OUT / "Module1.bas").write_bytes(BAS.encode("cp932"))
    (OUT / "Widget.cls").write_bytes(CLS.encode("cp932"))
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
