@echo off
:: Explicitly define the target path, working directory, and startup destination
set "TARGET_SCRIPT=C:\Users\Administrator\Desktop\oneapp\update_family.bat"
set "WORKING_DIR=C:\Users\Administrator\Desktop\oneapp"
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\update.lnk"

:: Verify the file exists before creating the shortcut
if not exist "%TARGET_SCRIPT%" (
    echo Error: update.bat was not found at:
    echo %TARGET_SCRIPT%
    pause
    exit /b
)

:: Build the VBScript snippet to generate the Windows shortcut (.lnk)
set "VBS_SCRIPT=%TEMP%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = "%SHORTCUT_PATH%" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%TARGET_SCRIPT%" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%WORKING_DIR%" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

:: Run the script and clean up the temporary VBS file
cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%"

echo Success! A startup shortcut has been created.
echo It will now start inside: %WORKING_DIR%
pause
