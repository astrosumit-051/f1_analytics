Option Explicit
Dim shell, fs, folder, rhome, rscript, base, child
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
rscript = ""
On Error Resume Next
rhome = shell.RegRead("HKLM\SOFTWARE\R-core\R\InstallPath")
On Error GoTo 0
If Len(rhome) > 0 Then
  If fs.FileExists(rhome & "\bin\Rscript.exe") Then rscript = rhome & "\bin\Rscript.exe"
End If
If Len(rscript) = 0 Then
  For Each base In Array(shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\R", shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\R")
    If fs.FolderExists(base) Then
      For Each child In fs.GetFolder(base).SubFolders
        If fs.FileExists(child.Path & "\bin\Rscript.exe") Then rscript = child.Path & "\bin\Rscript.exe"
      Next
    End If
  Next
End If
If Len(rscript) = 0 Then
  MsgBox "R was not found. Install R before opening F1 Analytics.", 48, "F1 Analytics"
  WScript.Quit 1
End If
shell.Run """" & rscript & """ --vanilla """ & folder & "\launch.R""", 0, False
