' ============================================================
'  Arid-Edge Sentinel  -  silent launcher (no cmd window)
'  Double-click for a demo-clean launch: hides the terminal,
'  Streamlit still opens the browser automatically.
'  Use the .bat instead if you want to see setup / error logs.
' ============================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

' Resolve script's own folder
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Build command: cd to folder, then run the .bat with window hidden
cmd = "cmd /c """"" & scriptDir & "\Launch Arid-Edge Sentinel.bat"""""

' 0 = hide window, False = don't wait for it to finish
WshShell.Run cmd, 0, False
