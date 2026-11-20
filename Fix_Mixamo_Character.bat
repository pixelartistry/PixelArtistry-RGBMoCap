@echo off
setlocal
title RGB MoCap - Fix Mixamo character (PixelArtistry)
cd /d "%~dp0"

echo ============================================================
echo  Fix a Mixamo character for RGB MoCap
echo  Drag the rigged FBX from Mixamo onto this file.
echo  Best: drag it together with the file you uploaded to Mixamo,
echo  so all of its textures can be restored.
echo ============================================================
echo.

set "BLENDER=%~dp0toyxyz_RGBMocap\runtime_character\blender.exe"
if not exist "%BLENDER%" (
    echo RGB MoCap is not installed yet. Run Install_RGBMoCap.bat first.
    pause
    exit /b 1
)
if "%~1"=="" (
    echo No file given. Drag the Mixamo FBX onto Fix_Mixamo_Character.bat.
    pause
    exit /b 1
)

set "LOG=%TEMP%\rgbmocap_fix_%RANDOM%.log"
"%BLENDER%" -b --factory-startup --python "%~dp0fix_mixamo_character.py" -- %* > "%LOG%" 2>&1
findstr /b /c:"FIX:" "%LOG%"
set "OUT="
for /f "usebackq tokens=1,* delims==" %%A in ("%LOG%") do if "%%A"=="FIX_OUTPUT" set "OUT=%%B"
del "%LOG%" 2>nul
if not defined OUT (
    echo.
    echo The fix did not finish - see the message above.
    pause
    exit /b 1
)

echo.
echo Checking the result with RGB MoCap's own character import ...
set "CHECK=%TEMP%\rgbmocap_charcheck_%RANDOM%"
mkdir "%CHECK%"
"%BLENDER%" -b --factory-startup --disable-autoexec --python-exit-code 1 --python "%~dp0toyxyz_RGBMocap\mocap\retarget\blender_entry.py" -- import "%CHECK%" "%OUT%" > "%CHECK%.log" 2>&1
if errorlevel 1 (
    echo   RGB MoCap cannot import it yet. The end of its log:
    powershell -NoProfile -Command "Get-Content -LiteralPath '%CHECK%.log' -Tail 8"
    rd /s /q "%CHECK%" 2>nul
    pause
    exit /b 1
)
rd /s /q "%CHECK%" 2>nul
del "%CHECK%.log" 2>nul

echo   OK - ready to import.
echo.
echo Saved: %OUT%
echo In RGB MoCap: File ^> Import Character... and pick that file.
pause
