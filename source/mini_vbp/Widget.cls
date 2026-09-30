VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
  Persistable = 0  'NotPersistable
  DataBindingBehavior = 0  'vbNone
  DataSourceBehavior  = 0  'vbNone
  MTSTransactionMode  = 0  'NotAnMTSObject
END
Attribute VB_Name = "Widget"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

Implements IPing

Private WithEvents Bus As AppEvents

Public Property Get Ready() As Boolean
Attribute Ready.VB_UserMemId = 0
    Ready = True
End Property

Public Function Ping(ByVal x As Long) As Long
    Ping = x
End Function

Public Sub PlaceHost()
    Form1.Left = 50
End Sub
