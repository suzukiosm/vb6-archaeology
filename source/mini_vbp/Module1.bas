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
