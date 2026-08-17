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

Public Sub IoDemo()
    Dim n As Long
    Open "tmp.dat" For Output As #1
    Put #1, , n
    Get #1, , n
    Close #1
    Name "tmp.dat" As "tmp.bak"
    Kill "tmp.bak"
End Sub

Public Sub SkipOpen()
    GoTo AfterSkip
    Open "modskip.dat" For Input As #3
AfterSkip:
End Sub
