@echo off
echo  ◆ TASKTRAY — Add to Windows Startup
echo.

set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\tasktray.vbs"

echo Creating startup entry...
(
echo Set WshShell = CreateObject("WScript.Shell"^)
echo WshShell.CurrentDirectory = "%SCRIPT_DIR%"
echo WshShell.Run chr(34^) ^& "%SCRIPT_DIR%.venv\Scripts\pythonw.exe" ^& chr(34^) ^& " " ^& chr(34^) ^& "%SCRIPT_DIR%server.py" ^& chr(34^), 0
echo Set WshShell = Nothing
) > "%VBS_PATH%"

echo.
echo  ✓ TaskTray will now start automatically with Windows.
echo    Startup file: %VBS_PATH%
echo.
echo  To remove: delete %VBS_PATH%
echo.
pause
