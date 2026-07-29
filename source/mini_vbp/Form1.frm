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
