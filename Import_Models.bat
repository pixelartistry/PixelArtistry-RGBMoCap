@echo off
title RGB MoCap - Import Models (PixelArtistry)
cd /d "%~dp0"

echo ============================================================
echo  RGB MoCap - download missing models + import your files
echo  Looks in "gated_downloads" and in your Downloads folder
echo ============================================================
echo.

where uv >nul 2>nul
if errorlevel 1 set "PATH=%USERPROFILE%\.local\bin;%PATH%"

uv run --python 3.11 --no-project install_rgbmocap.py --models-only %*
if errorlevel 1 (
    echo.
    echo Stopped - scroll up for the message, or open install_log.txt.
    pause
    exit /b 1
)

echo.
pause
