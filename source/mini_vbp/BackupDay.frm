VERSION 5.00
Begin VB.Form Form12
   Caption         =   "•Ê–¼‰æ–Ê"
   ClientHeight    =   2000
   ClientWidth     =   3000
   Height          =   2400
   Left            =   120
   Top             =   120
   Width           =   3120
   Begin VB.CommandButton Command1
      Caption         =   "•Â‚¶‚é"
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
