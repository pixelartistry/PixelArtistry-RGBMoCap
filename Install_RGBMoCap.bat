@echo off
title RGB MoCap - One-Click Installer (PixelArtistry)
cd /d "%~dp0"

echo ============================================================
echo  RGB MoCap - One-Click Installer by PixelArtistry
echo  Needs: Windows 10/11 64-bit, NVIDIA GPU, ~65 GB free disk
echo ============================================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv ^(Python package manager^)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv run --python 3.11 --no-project install_rgbmocap.py %*
if errorlevel 1 (
    echo.
    echo Installation stopped - scroll up for the message, or open install_log.txt.
    echo You can start this file again: finished parts are kept.
    pause
    exit /b 1
)

echo.
echo Done. Read the "Result" section above, then double-click Run_RGBMoCap.bat.
pause
