@echo off
setlocal
cd /d "%~dp0"
py -3.14 -m PyInstaller --noconfirm --distpath . --workpath "%TEMP%\MobileGameLaunchpad-build" MobileGamePlayOnce.spec
if errorlevel 1 (
    echo Build failed. Close MobileGameLaunchpad.exe before building.
    echo Install dependencies first: py -3.14 -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo Build complete: MobileGameLaunchpad.exe
pause
