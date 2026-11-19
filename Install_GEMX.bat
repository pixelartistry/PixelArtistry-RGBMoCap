@echo off
title RGB MoCap - GEM-X add-on (PixelArtistry)
cd /d "%~dp0"

echo ============================================================
echo  RGB MoCap - optional GEM-X add-on
echo  NVIDIA's model: one person, fixed camera, clips up to 60 s
echo  Needs: RGB MoCap installed, NVIDIA driver 580+, ~20 GB free
echo ============================================================
echo.
echo GEM-X is the one motion model in RGB MoCap that is not tied to
echo research-only licences. Its parts still have their own terms.
echo Please read them before you continue:
echo.
echo   GEM-X code      https://github.com/NVlabs/GEM-X/blob/4aef1452e5df171deff4f293c08e643eb450981e/LICENSE
echo   GEM-X model     https://huggingface.co/nvidia/GEM-X
echo   SOMA-X body     https://huggingface.co/nvidia/SOMA-X
echo   Person detector https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose
echo.
choice /c YN /n /m "I have read the terms and want to install GEM-X. Continue? [Y/N] "
if not "%errorlevel%"=="1" exit /b 1
echo.

where uv >nul 2>nul
if errorlevel 1 set "PATH=%USERPROFILE%\.local\bin;%PATH%"

uv run --python 3.11 --no-project install_rgbmocap.py --gemx
if errorlevel 1 (
    echo.
    echo Stopped - scroll up for the message, or open install_log.txt.
    pause
    exit /b 1
)

echo.
echo Done. Start Run_RGBMoCap.bat and pick GEM-X under "AI Motion Model".
pause
