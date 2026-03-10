@echo off
echo  ◆ CMD CENTER — Add to Windows Startup
echo.

:: Create a VBS script that launches silently (no console window)
set "SCRIPT_DIR=%~dp0"
set "VBS_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\cmd-center.vbs"

echo Creating startup entry...
(
echo Set WshShell = CreateObject("WScript.Shell"^)
echo WshShell.Run chr(34^) ^& "%SCRIPT_DIR%start.bat" ^& chr(34^), 0
echo Set WshShell = Nothing
) > "%VBS_PATH%"

echo.
echo  ✓ CMD Center will now start automatically with Windows.
echo    Startup file: %VBS_PATH%
echo.
echo  To remove: delete %VBS_PATH%
echo.
pause
