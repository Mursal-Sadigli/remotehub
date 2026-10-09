Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d ""c:\Users\fullm\Downloads\RemoteHub"" && .venv\Scripts\pythonw.exe pc_agent.py", 0, False
